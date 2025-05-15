import subprocess
import time


def run_command(cmd, task_name, environment):
    start_time = time.time()
    try:
        result = subprocess.run(
            cmd,
            check=True,
            capture_output=True,
            text=True
        )
        environment.events.request.fire(
            request_type="DOCKER",
            name=task_name,
            response_time=round((time.time() - start_time) * 1000, 5),
            response_length=len(result.stdout),
        )
        return True
    except subprocess.CalledProcessError as e:
        environment.events.request.fire(
            request_type="DOCKER",
            name=task_name,
            response_time=round((time.time() - start_time) * 1000, 5),
            exception=e,
        )
        return False
