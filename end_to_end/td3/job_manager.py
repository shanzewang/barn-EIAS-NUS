import os
import subprocess
from os.path import join, exists

import htcondor  # for submitting jobs, querying HTCondor daemons, etc.
import classad   # for interacting with ClassAds, HTCondor's internal data format

# The JobStatus is an integer; the integers map into the following states:
#  - 1: Idle (I) 
#  - 2: Running (R) 
#  - 3: Removed (X)
#  - 4: Completed (C)
#  - 5: Held (H)
#  - 6: Transferring Output
#  - 7: Suspended

class CondorJob(object):
    def __init__(self, exe, arguments):
        self.exe = exe
        self.arguments = arguments
        self.cluster = self.submit(exe, arguments)
        self.schedd = htcondor.Schedd()

    def submit(self, exe, arguments):
        log_name = exe.replace("/", "-") + "-" + str(arguments).split(" ")[-1]
        BUFFER_PATH = os.getenv("BUFFER_PATH")
        submission_file = os.path.join(BUFFER_PATH, 'actors.sub')
        cfile = open(submission_file, 'w')
        common_command = "\
            requirements       = InMastodon \n\
            +Group              = \"GRAD\" \n\
            +Project            = \"AI_ROBOTICS\" \n\
            +ProjectDescription = \"Adaptive Planner Parameter Learning From Reinforcement\" \n\
            Executable          = %s \n\
            Universe            = vanilla\n\
            getenv              = true\n\
            transfer_executable = false \n\n" %(exe)
        cfile.write(common_command)

        # Add actor arguments
        run_command = "\
            arguments  = %d\n\
            output     = %s\n\
            log        = %s\n\
            error      = %s\n\
            queue 1\n\n" % (
                arguments,
                join(BUFFER_PATH, "out", "out-" + log_name + ".txt"),
                join(BUFFER_PATH, "out", "log-" + log_name + ".txt"),
                join(BUFFER_PATH, "out", "err-" + log_name + ".txt")
            )
        cfile.write(run_command)

        cfile.close()

        out = subprocess.run(["condor_submit", submission_file], stdout=subprocess.PIPE)
        return str(out.stdout).split("to cluster ")[-1].split(".")[0]

    def check_job_status(self):
        return self.schedd.query(
            constraint='ClusterId =?= {}'.format(self.cluster),
            projection=["ClusterId", "ProcId", "JobStatus", "EnteredCurrentStatus"],
        )

    def recover_job(self):
        # check job status, if it's done or hold, then Vacate the job
        job_status = self.check_job_status()
        if job_status["JobStatus"] not in [1, 2, 6]:
            self.Remove()
            self.cluster = self.submit(self.exe, self.arguments)

    def Vacate(self):
        self.schedd.act(htcondor.JobAction.Vacate, f"ClusterId == {self.cluster}")

    def Hold(self):
        self.schedd.act(htcondor.JobAction.Hold, f"ClusterId == {self.cluster}")

    def Remove(self):
        self.schedd.act(htcondor.JobAction.Remove, f"ClusterId == {self.cluster}")

    def Release(self):
        self.schedd.act(htcondor.JobAction.Release, f"ClusterId == {self.cluster}")       


if __name__ == "__main__":
    import time
    for _ in range(1):
        job = CondorJob("executable/actor.sh", 0)
    for i in range(10):
        time.sleep(1)
        print(i, end="\r")
    job.Vacate()
    # job.Remove()