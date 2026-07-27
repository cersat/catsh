from pathlib import Path
import os
import sys
import shutil
import json
import requests
import subprocess

scr_args = sys.argv[1:]
debug   = "--debug"   in scr_args
fullerr = "--fullerr" in scr_args
showver = "--ver"     in scr_args
osname = os.name
if osname == 'nt':
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
script_path = os.path.abspath(__file__)
current_dir = os.path.dirname(os.path.abspath(script_path))
catver = "Catsh V0.04"
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
    
def print_dir(folder, use_a, use_d, use_f, use_z, use_s, use_r, count=0):
    for item in folder.iterdir():
        if (item.is_file() and use_f) or (item.is_dir() and use_d) or (item.is_symlink() and use_z):
            if use_s in item.name:
                print(item.name)
                count += 1
                
        if use_r and item.is_dir():
            if fullerr:
                 count = print_dir(item, use_a, use_d, use_f, use_z, use_s, use_r, count)
            else:
                try:
                    count = print_dir(item, use_a, use_d, use_f, use_z, use_s, use_r, count)
                except PermissionError:
                    errprint(1, item.name, "is inaccessible")
        if count >= use_a:
            break
    return count
    
def split_args(line):
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
        
# commands

def cmd_ver(args):
    print(catver)
    
def cmd_quit(args):
    print("exiting catsh")
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
        print("Usage: catsee <folder> [-f -d -z -a N -s STR]")
        print("-f show files")
        print("-d show folders")
        print("-z show links")
        print("-a N show only first N files")
        print("-s STR search for STR")
        return
    use_f = '-f' in args
    use_d = '-d' in args
    use_z = '-z' in args
    use_r = '-r' in args
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
        errprint(2, "-a and -s cannot appear at the end of the line.")
        return
    except ValueError:
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
        print_dir(folder_path, use_a, use_d, use_f, use_z, use_s, use_r)
    else:
        try:
            print_dir(folder_path, use_a, use_d, use_f, use_z, use_s, use_r)
        except PermissionError:
            errprint(1, folder_path, "is inaccessible")

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
        print("Usage: mkdir <folder>")
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
        print("Usage: run <script>")
        return
    script = args[0]
    rscript()
    
def cmd_cmddef(args):
    help   = "/?" in args
    delete = "/d" in args
    check  = "/c" in args
    global commands
    if (len(args) < 2 and not check) or help:
        print("CATSH cmddef V1.01")
        print("Usage: cmddef [/? /d /c]<command> <code>")
        print("/? - this help message")
        print("/d - delete alias")
        print("/c - find another cmddef installed")
        return
    elif delete:
        del commands[args[1]]
        save_aliases()
    elif check:
        print("CATSH cmddef v1.01 -- this program")
        if Path("C:/Program files/cmddef/").is_dir():
            print("BATCH cmddef in C:/program files/cmddef")
    elif args[0] != args[1]:
        commands[args[0]] = " ".join(args[1:])
        save_aliases()
    else:
        print("cannot create recursive command")
        
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
    response = requests.get(url, timeout=10)
    data = response.text
    dbgprint("downloaded file")
    with open("catsh_.py", "w") as f:
        f.write(data)
    dbgprint("running file")
    result = subprocess.run(["python", "catsh_.py", "--ver"], capture_output=True, text=True)
    itver = float(result.stdout[7:])
    myver = float(catver[7:])
    if itver > myver: 
        Path("catsh_.py").replace(Path(__file__))
    else:
        os.remove("catsh_.py")
        
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
}

# R.I.P "nothing\" folder
def runcmd(cmd):
    global keep_cycle
    if not cmd:
        return
    cmd_args = split_args(cmd)
    args = cmd_args[1:]
    command = cmd_args[0]
    if fullerr:
        action = commands[command]
        if callable(action):
            action(args)
        elif isinstance(action, str):
            runcmd(action + " " + " ".join(args))
    else:
        try:
            action = commands[command]
            if callable(action):
                action(args)
            elif isinstance(action, str):
                runcmd(action + " " + " ".join(args))
        except KeyError:
            errprint(3, "invalid command")
        except RecursionError:
            errprint(2, "recursive command")
        except KeyboardInterrupt:
            print("exiting catsh")
            keep_cycle = False
        except Exception as e:
            errprint(3, "unknown error:", e)

def rscript():
    dbgprint("Running", script)
    script_lines = []
    if script:
        with open(script, encoding="utf-8") as f:
            script_lines = f.read().splitlines()
    i = 0
    while keep_cycle:
        try:
            cmd = script_lines[i]
        except IndexError:
            return
        i = i + 1
        runcmd(cmd)

def main():
    global keep_cycle
    if showver:
        print(catver, end='')
        return
    load_aliases()
    dbgprint("Debug prints are turned on")
    print(catver)
    if script:
        rscript()
        return
    while keep_cycle:
        if fullerr:
            cmd = input(current_dir + ">")
        else:
            try:
                cmd = input(current_dir + ">")
            except EOFError:
                print("exiting catsh")
                keep_cycle = False
                continue
            except KeyboardInterrupt:
                print("exiting catsh")
                keep_cycle = False
                continue
        runcmd(cmd)

if __name__ == "__main__":
    main()