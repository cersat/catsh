from pathlib import Path
import os
import sys
import shutil
import json
import urllib.request
from urllib.parse import quote
import subprocess
from datetime import datetime
import threading
import queue
import time

script_line = 0
q = queue.Queue()
stop_flag = threading.Event()
flags     = {}
variables = {}
scr_args = sys.argv[1:]
debug    = "--debug"    in scr_args
fullerr  = "--fullerr"  in scr_args
showver  = "--ver"      in scr_args
portable = "--portable" in scr_args
script_path = os.path.abspath(__file__)
current_dir = os.path.dirname(os.path.abspath(script_path))
osname = os.name
if portable:
    catsh_dir = os.path.dirname(os.path.abspath(script_path))
elif osname == 'nt':
    appdata = os.environ.get("APPDATA", os.path.expanduser("~\\AppData\\Roaming"))
    catsh_dir = os.path.join(appdata, "Catsh")
else:
    config_home = os.environ.get("XDG_CONFIG_HOME", os.path.expanduser("~/.config"))
    catsh_dir = os.path.join(config_home, "Catsh")
aliases_path = os.path.join(catsh_dir, "aliases.json")
os.makedirs(catsh_dir, exist_ok=True)
try:
    script  = scr_args[scr_args.index("-s") + 1]
except ValueError:
    script  = False
keep_cycle  = True

catver = "Catsh V0.15"
def dbgprint(*args):
    if debug:
        print("[DEBUG]", *args)
      
def errprint(err_power, *args):
    print('!' * err_power, *args)

        
def presolve(arg):
    p = Path(arg)
    if p.is_absolute():
        return p
    return Path(current_dir) / arg
    
def print_dir(folder, use_a, use_d, use_f, use_z, use_s, use_r, use_e, count=0):
    for item in folder.iterdir():
        if (item.is_file() and use_f) or (item.is_dir() and use_d) or (item.is_symlink() and use_z):
            if use_s in item.name:
                if use_r:
                    print(folder + '\\' + item.name)
                else:
                    print(item.name)
                count += 1
                
        if use_r and item.is_dir():
            if fullerr:
                 count = print_dir(item, use_a, use_d, use_f, use_z, use_s, use_r, use_e, count)
            else:
                try:
                    count = print_dir(item, use_a, use_d, use_f, use_z, use_s, use_r, use_e, count)
                except PermissionError:
                    if not use_e:
                        errprint(1, item.name, "is inaccessible")
        if count >= use_a:
            break
    return count
    
def update_constants():
    now = datetime.now()
    variables["cwd"]    = current_dir
    variables["catsh"]  = catsh_dir
    variables["year"]   = now.strftime("%Y")
    variables["month"]  = now.strftime("%m")
    variables["day"]    = now.strftime("%d")
    variables["hour"]   = now.strftime("%H")
    variables["minute"] = now.strftime("%M")
    variables["second"] = now.strftime("%S")
    variables["input"]  = '' # placeholder
    
def parse_vars(line):
    global variables
    global keep_cycle
    update_constants()
    out_line = ''
    var_line = ''
    is_var = False
    prev = ''
    for i in line:
        if i == '%':
            if prev == '^':
                out_line = out_line[:-1]
                out_line += i
            else:
                if is_var:
                    if var_line == "input":
                        variables["input"] = input()
                        out_line += variables[var_line]
                        var_line = ''
                    elif var_line in variables.keys():
                        out_line += variables[var_line]
                        var_line = ''
                    else:
                        out_line += '%' + var_line + '%'
                        var_line = ''
                is_var = not is_var
        elif is_var:
            var_line += i
        else:
            out_line += i
        prev = i
    return out_line
    
def split_args(line):
    line = parse_vars(line)
    args = []
    current = ""
    in_quotes = False
    for ch in line:
        if ch == '"':
            in_quotes = not in_quotes
        elif ch == ' ' and not in_quotes:
            if current:
                args.append(current)
                current = ""
        else:
            current += ch
    if current:
        args.append(current)
    return args
    
def load_aliases():
    try:
        with open(aliases_path, "r", encoding="utf-8") as f:
            saved = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return
    commands.update(saved)

def save_aliases():
    aliases = {name: body for name, body in commands.items()
               if isinstance(body, str)}
    with open(aliases_path, "w", encoding="utf-8") as f:
        json.dump(aliases, f, ensure_ascii=False, indent=2)

def input_thread(nickname):
    while True:
        try:
            line = input(nickname + ':')
            q.put(line)
            if stop_flag.is_set() or line == "EXIT":
                stop_flag.set()
                break
        except Exception:
            q.put('EXIT')
            stop_flag.set()
            break
        
def net_thread(room, nickname):
    own_prefix = nickname + ": "
    response = urllib.request.urlopen(f"https://ntfy.sh/{room}/json")
    for line in response:
        if stop_flag.is_set():
            break
        if not line.strip():
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if stop_flag.is_set():
            break
        if event.get("event") != "message":
            continue
        message = event.get("message", "")
        if stop_flag.is_set():
            break
        if message == "__ping__":
            urllib.request.urlopen("https://ntfy.sh/" + room, data=b"__pong__")
        elif message == "__pong__":
            continue
        elif message.startswith(own_prefix):
            continue
        else:
            print(message)
        
# commands

def cmd_ver(args):
    print(catver)
    
def cmd_quit(args):
    global keep_cycle
    keep_cycle = False
    
def cmd_type(args):
    if not args:
        print("Usage: type <file>")
        return
    with open(presolve(args[0]), "r") as file:
        content = file.read()
        print(content)

def cmd_catsee(args):
    if not args:
        print("Usage: catsee <folder> [-f -d -z -a N -s STR -r -e]")
        print("-f show files")
        print("-d show folders")
        print("-z show links")
        print("-a N show only first N files")
        print("-s STR search for STR")
        print("-r show recursive")
        print("-e ignore errors")
        return
    use_f = '-f' in args
    use_d = '-d' in args
    use_z = '-z' in args
    use_r = '-r' in args
    use_e = '-e' in args
    try:
        if '-a' in args: 
            use_a = int(args[args.index('-a') + 1])
        else:
            use_a = 10
        
        if '-s' in args: 
            use_s = args[args.index('-s') + 1]
        else:
            use_s = ''
    except IndexError:
        if not use_e:
            errprint(2, "-a and -s cannot appear at the end of the line.")
        return
    except ValueError:
        if not use_e:
            errprint(2, "there must be a number after -a.")
        return
    
    if len(args) == 1:
        errprint(1, "no filters specified, processing with '-f -d -z -a 10'")
        use_f = True
        use_d = True
        use_z = True
        use_a = 10
        use_s = ''
    folder_path = Path(current_dir)
    if args[0] != ".":
        folder_path = presolve(args[0])
    
    if fullerr:
        print_dir(folder_path, use_a, use_d, use_f, use_z, use_s, use_r, use_e)
    else:
        try:
            print_dir(folder_path, use_a, use_d, use_f, use_z, use_s, use_r, use_e)
        except PermissionError:
            if not use_e:
                errprint(2, folder_path, "is inaccessible")

def cmd_echo(args):
    for arg in args:
        print(arg, end=' ')
    print()
        
def cmd_cd(args):
    if not args:
        print("Usage: cd <folder> <folder> <folder>...")
        return
    global current_dir
    path_backup = current_dir
    for arg in args:
        base_path = Path(current_dir)
        if arg == "..":
            current_dir = Path(current_dir).parent
        else:
            current_dir = base_path / arg
    if current_dir.exists():
        current_dir = str(current_dir)
    else:
        current_dir = path_backup
        print("incorrect path!")
        
def cmd_rem(args):
    pass
    
def cmd_mdir(args):
    if not args:
        print("Creates folder")
        print("Usage: mdir <folder>")
        return
    presolve(args[0]).mkdir(exist_ok=True)
        
def cmd_rm(args):
    if not args:
        print("Usage: <files> [-r -d -s -q]")
        print("-r - recursive deleting")
        print("-d - remove empty folder")
        print("-s - smart deleting for files and empty folders")
        print("-q - quiet mode")
        return
    recursive = "-r" in args 
    rec_ok    = recursive and (input("write 'DeLeTe' to proceed: ") == "DeLeTe")
    only_dir  = "-d" in args
    smart     = "-s" in args
    quiet     = "-q" in args
    targets = [a for a in args if not a.startswith("-")]

    if not targets:
        errprint(2, "no target for removing")
        return

    for target in targets:
        target = presolve(target)
        if not quiet:
            print("deleting", target)
        
        if recursive and rec_ok:
            shutil.rmtree(target)
        elif smart:
            if target.is_dir():
                if any(target.iterdir()):
                    if not quiet:
                        errprint(1, "this folder is not empty")
                else:
                    target.rmdir()
            else:
                target.unlink()
        elif only_dir:
            target.rmdir()
        elif not recursive:
            target.unlink()
        else:
            if not quiet:
                print("passed", target)
    
def cmd_move(args):
    if len(args) < 2:
        print("Usage: move <src> <dst>")
        return
    shutil.move(presolve(args[0]), presolve(args[1]))
    
def cmd_copy(args):
    if len(args) < 2:
        print("Usage: copy <src> <dst>")
        return
    shutil.copy(presolve(args[0]), presolve(args[1]))
   
def cmd_run(args):
    global script
    if not args:
        print("Usage: run <script> or run --out <filename.ext>")
        return
    if args[0] == "--out":
        if len(args) > 1:
            os.system(args[1])
        else:
            errprint(2, "script for execution not received")
    else:
        previous_script = script
        script = args[0]
        rscript()
        script = previous_script
    
def cmd_cmddef(args):
    help   = "/?" in args
    delete = "/d" in args
    check  = "/c" in args
    list   = "/l" in args
    global commands
    if not args or help:
        print("CATSH cmddef V1.02")
        print("Usage: cmddef [/? /d /c /l]<command> <code>")
        print("/? - this help message")
        print("/d - delete alias")
        print("/c - find another cmddef installed")
        print("/l - list aliases")
        return
    elif delete and len(args) > 1:
        if args[1] in commands:
            del commands[args[1]]
            save_aliases()
        else:
            errprint(2, "no such alias")
    elif list:
        for command, func in commands.items():
            if isinstance(func, str):
                print(command)
    elif check:
        print("CATSH cmddef v1.02 -- this program")
        if Path("C:/Program files/cmddef/").is_dir():
            print("BATCH cmddef in C:/program files/cmddef")
    elif len(args) == 1:
        if args[0] in commands and isinstance(commands[args[0]], str):
            print(commands[args[0]])
        else:
            errprint(2, "no such alias")
    else: #if len(args) > 1:
        if args[1].split()[0] == args[0]:
            errprint(2, "cannot create recursive command")
        else:
            if not (args[1].split())[0] in commands:
                errprint(1, "no such command:", args[1])
            if args[0] in commands:
                errprint(1, "redeclaration:", args[0], "already exists")
            commands[args[0].lower()] = args[1]
            save_aliases()
        
def cmd_help(args):
    global commands
    for i in commands.keys():
        print(i)
      
def cmd_cls(args):
    if osname == 'nt':
        os.system('cls')
    else:
        os.system('clear')
        
def cmd_update(args):
    url = "https://raw.githubusercontent.com/cersat/catsh/main/catsh.py"
    try:
        with urllib.request.urlopen(url, timeout=10) as response:
            data = response.read().decode("utf-8")
        dbgprint("downloaded file")
        with open("catsh_.py", "w") as f:
            f.write(data)
        dbgprint("running file")
        result = subprocess.run(["python3", "catsh_.py", "--ver"], capture_output=True, text=True)
        itver = float(result.stdout[7:])
        myver = float(catver[7:])
        if itver > myver: 
            Path("catsh_.py").replace(Path(__file__))
            print("updated catsh to", itver)
        else:
            os.remove("catsh_.py")
            print("catsh is up-to-date")
    except urllib.error.URLError:
        errprint(2, "no internet connection")
        
def cmd_set(args):
    if not args or '=' not in args[0]:
        print('Usage: set "var=value"')
        return
    var, value = args[0].split('=', 1)
    variables[var] = value
    
def cmd_env(args):
    global variables
    for k, v in variables.items():
        print(k, '=', v, sep='')
        
def cmd_touch(args):
    if not args:
        print("Create files")
        print("Usage: touch <file> <file> <file>...")
        return
    for file in args:
        if os.path.exists(str(presolve(file))):
            print(file, "already exists")
        presolve(file).touch()
        
def cmd_bridge(args):
    stop_flag.clear()
    if len(args) < 2:
        print("NetBridge V1.01")
        print("Usage: bridge <room id> <nickname>")
        return
    room = quote(args[0], safe='')
    nickname = args[1]

    urllib.request.urlopen("https://ntfy.sh/" + room, data=b"__ping__")
    time.sleep(1.5)
    response = urllib.request.urlopen(f"https://ntfy.sh/{room}/json?poll=1&since=all")
    is_admin = True
    for line in response:
        if not line.strip():
            continue
        event = json.loads(line)
        if event.get("event") == "message" and event.get("message") == "__pong__":
            is_admin = False

    if is_admin:
        urllib.request.urlopen("https://ntfy.sh/" + room, data=b"room opened")
    else:
        urllib.request.urlopen("https://ntfy.sh/" + room, data=(nickname + " connected").encode())

    threading.Thread(target=input_thread, args=(nickname, ), daemon=True).start()
    threading.Thread(target=net_thread, args=(room, nickname), daemon=True).start()

    line = ''
    while line != 'EXIT':
        try:
            line = q.get(timeout=1)
            if line != 'EXIT':
                urllib.request.urlopen("https://ntfy.sh/" + room, data=(nickname + ": " + line).encode())
        except queue.Empty:
            pass
    stop_flag.set()
    
def cmd_pause(args):
    input(args[0] if args else "press enter to continue")
   
def cmd_goto(args):
    global script_line
    if not script or not args:
        print("Scripts only")
        print("Usage: goto <flag>")
        return
    
    if len(args) < 3 or args[1] == args[2]:
        script_line = flags[args[0]]
        
def cmd_sleep(args):
    if not args:
        print("Usage: sleep <seconds>")
        return
    time.sleep(int(args[0]))
    
def cmd_thread(args):
    if not args:
        print("Usage: thread <command> <command> <command>...")
        return
    for arg in args:
        threading.Thread(target=runcmd, args=(arg,), daemon=True).start()
        
def cmd_write(args):
    if len(args) < 2:
        print("Usage:")
        print("write --interactive <file>")
        print("write <file> <string> <string> <string>...")
        return
    
    if args[0] == "--interactive":
        prent = ''
        file = presolve(args[1])
        print("enter EXIT to exit")
        file.touch(exist_ok=True)
        prent = input(file.name + '>')
        while prent != 'EXIT':
            with open(file, "a", encoding="utf-8") as f:
                f.write(prent + "\n")
            prent = input(file.name + '>')
        print("exiting write")
    else:
        file = presolve(args[0])
        strings = args[1:]
        for string in strings:
            with open(file, "a", encoding="utf-8") as f:
                f.write(string + "\n")
    

# commands end

commands = {
    "ver"   : cmd_ver,
    "quit"  : cmd_quit,
    "type"  : cmd_type,
    "catsee": cmd_catsee,
    "echo"  : cmd_echo,
    "cd"    : cmd_cd,
    "rem"   : cmd_rem,
    "mdir"  : cmd_mdir,
    "rm"    : cmd_rm,
    "move"  : cmd_move,
    "copy"  : cmd_copy,
    "run"   : cmd_run,
    "cmddef": cmd_cmddef,
    "help"  : cmd_help,
    "cls"   : cmd_cls,
    "update": cmd_update,
    "set"   : cmd_set,
    "env"   : cmd_env,
    "touch" : cmd_touch,
    "bridge": cmd_bridge,
    "pause" : cmd_pause,
    "goto"  : cmd_goto, # scripts only
    "sleep" : cmd_sleep,
    "thread": cmd_thread,
    "write" : cmd_write,
}

# R.I.P "nothing\" folder
def runcmd(cmd):
    global keep_cycle
    if cmd.startswith(":"):
        return
    if fullerr:
        cmd_args = split_args(cmd)
    else:
        try:
            cmd_args = split_args(cmd)
        except BaseException:
            return
    if not cmd_args:
        return
    args = cmd_args[1:]
    command = cmd_args[0].lower()
    if fullerr:
        action = commands[command]
        if callable(action):
            action(args)
        elif isinstance(action, str):
            full_args = ''
            for i, arg in enumerate(args):
                full_args += ' ' + arg
                variables[str(i)] = arg
            variables['*'] = full_args
            runcmd(action)
            del variables['*']
            for i, arg in enumerate(args):
                del variables[str(i)]
    else:
        try:
            action = commands[command]
            if callable(action):
                action(args)
            elif isinstance(action, str):
                full_args = ''
                for i, arg in enumerate(args):
                    full_args += ' ' + arg
                    variables[str(i)] = arg
                variables['*'] = full_args
                runcmd(action)
                del variables['*']
                for i, arg in enumerate(args):
                    del variables[str(i)]
        except KeyError:
            errprint(3, "invalid command:", command)
        except RecursionError:
            errprint(3, "recursive command")
        except KeyboardInterrupt:
            pass
        except OSError as e:
            errprint(3, "file system error:", e.strerror)
        except Exception as e:
            errprint(3, "unknown error of", type(e).__name__ + ':', str(e))

def rscript():
    global script_line
    script_running = True
    dbgprint("Running", script)
    script_lines = []
    if script:
        with open(script, encoding="utf-8") as f:
            script_lines = f.read().splitlines()
    script_line = 0
    while True:
        try:
            cmd = script_lines[script_line]
        except IndexError:
            break
        script_line = script_line + 1
        if cmd.startswith(":"):
            flags[cmd[1:]] = script_line
    script_line = 0
    while keep_cycle and script_running:
        try:
            cmd = script_lines[script_line]
        except IndexError:
            script_running = False
            continue
        script_line = script_line + 1
        runcmd(cmd)
    if not "startup.csh" in script:
        print("exiting", script)

def main():
    global keep_cycle
    global variables
    global script
    #global *
    variables["prompt"] = "%cwd%>"
    if showver:
        print(catver, end='')
        return
    load_aliases()
    dbgprint("Debug prints are turned on")
    if (Path(catsh_dir) / "startup.csh").is_file():
        previous_script = script
        script = str(Path(catsh_dir) / "startup.csh")
        rscript()
        script = previous_script
    print(catver)
    if script:
        rscript()
        return
    while keep_cycle:
        if fullerr:
            cmd = input(parse_vars(variables["prompt"]))
        else:
            try:
                cmd = input(parse_vars(variables["prompt"]))
            except EOFError:
                return
            except KeyboardInterrupt:
                keep_cycle = False
                continue
        runcmd(cmd)
    print("exiting catsh")

if __name__ == "__main__":
    main()