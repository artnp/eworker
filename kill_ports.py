import os
import subprocess

def kill_port(port):
    try:
        output = subprocess.check_output(f'netstat -ano | findstr :{port}', shell=True).decode()
        for line in output.splitlines():
            if 'LISTENING' in line:
                pid = line.strip().split()[-1]
                print(f"Killing PID {pid} on port {port}")
                os.system(f'taskkill /F /PID {pid}')
    except Exception as e:
        print(f"No process found on port {port} or error: {e}")

if __name__ == '__main__':
    kill_port(5000)
    kill_port(5001)
