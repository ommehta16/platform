import subprocess, os
from subprocess import Popen, PIPE
import time

olddir = os.getcwd()

def elim_whitespace(a: str) -> str:
    '''
    sanitizes whitespace for each line individually
    '''
    strippedLines = list(map(str.rstrip, a.splitlines()))
    return "\n".join(strippedLines).replace("\r","")

def grade(file, tests, language):
    '''
     Takes in a filename and testcases and runs it using each test case

     For each test case:
       - If the program takes over `TIME_LIMIT` to execute, it returns `"Time Limit Exceeded"` for that testcase
       - If the program produces incorrect output, it returns `"Wrong Answer"`
       - If the program crashes, it returns `"Runtime Error"`
       - Otherwise, it returns `"Accepted"`
    '''

    results = []
    
    os.chdir(olddir)
    os.chdir("/".join(file.split("/")[:-1]))

    file = file.split("/")[-1]
    # compile
    if language == "java":
        Popen(["javac", file], stdout=PIPE, stderr=PIPE).communicate()
        # test if compilation was successful
        if not os.path.isfile(file.split(".")[0] + ".class"):
            print("java compilation error")
            os.chdir(olddir)
            return [["CE", "Compile Error"]]
        print("java compilation successful")
    elif language == "cpp":
        Popen(["g++", file], stdout=PIPE, stderr=PIPE).communicate()
        # test if compilation was successful
        if not os.path.isfile("a.out"):
            print("c++ compilation failed")
            os.chdir(olddir)
            return [["CE","Compile Error"]]
        print("cpp compilation successful")

    # execute
    for test in tests:
        data, solution = test
        time_start = time.perf_counter_ns()
        if language == "python":
            print(f"running {file} (python)")
            process = Popen(["python3", file], stdout=PIPE, stderr=PIPE, stdin=PIPE, text=True)
            TIME_LIMIT = 4
        elif language == "python2":
            print(f"running {file} (python)")
            process = Popen(["python2.7", file], stdout=PIPE, stderr=PIPE, stdin=PIPE, text=True)
            TIME_LIMIT = 4
        elif language == "java":
            process = Popen(["java", file.split(".")[0]], stdout=PIPE, stderr=PIPE, stdin=PIPE, text=True)
            TIME_LIMIT = 2
        elif language == "cpp":
            process = Popen(["./a.out"], stdout=PIPE, stderr=PIPE, stdin=PIPE, text=True)
            TIME_LIMIT = 1
        try:
            output = process.communicate(input = elim_whitespace(str(data)), timeout = TIME_LIMIT)
            time_elapsed = (time.perf_counter_ns() - time_start)//1000000
        except subprocess.TimeoutExpired:
            process.kill()
            print("time limit exceeded on test", len(results))
            results.append(["TLE","--"])
            continue
        if output[1] != "": # Some error happened
            print(output[1])
            results.append(["RE", time_elapsed])
            continue

        out:str = elim_whitespace(output[0])
        sol:str = elim_whitespace(solution)
        
        if out == sol:
            results.append(["AC", time_elapsed])
            continue
        else: # Output doesn't match
            # print("input was:", str(data))
            # print("program outputted:", output[0])
            # print("correct solution:", solution)
            print("wrong answer on test", len(results))
            results.append(["WA", time_elapsed])
    os.chdir(olddir)
    return results

if __name__ == "__main__":
    print(grade("hello.py", [[1,"hello world!\n"], [2,"hello world!\n"*2]], "python2"))
