# Bash — Supplement

> Added by Megamind. This is not from your original notes. Corrections first, then the core Bash features the notes don't cover yet.

## Corrections to the notes

- **No spaces around `=` in assignments.** `name = "mohamed"` makes Bash try to run a command called `name`. Write `name="mohamed"`. The same applies to `export`: `export MYVAR="any string"`.
- **Running a script:** use `bash scriptname.sh` (not `python bash scriptname.sh`), or `chmod +x scriptname.sh` and then `./scriptname.sh`.
- The shebang is usually written without a space: `#!/bin/bash` (or `#!/usr/bin/env bash` to find bash on the PATH).
- Inside `[[ ]]`, `==` compares **strings**. For numbers use `-eq -lt -gt ...` or arithmetic `(( x == y ))`.
- In loops, reference variables with `$`: `while [[ $x -le 100 ]]`.

## Quoting

- `"double quotes"` expand variables and command substitution: `"Hi $name"`.
- `'single quotes'` are literal: `'Hi $name'` prints `$name`.
- Always quote variables that might contain spaces: `rm "$file"`, not `rm $file`.

## Functions

```bash
greet() {
  local name="$1"          # local = only visible inside the function
  echo "Hello, $name"
  return 0                 # return sets the exit status (0-255), not a value
}

greet "Yahia"
result=$(greet "Yahia")    # capture output to "return" a string
```

Inside a function `$1 $2 ...` are the function's arguments, `$#` is the argument count, and `$@` is all arguments.

## Special variables

| Variable | Meaning |
|---|---|
| `$0` | script name |
| `$1 … $9` | positional arguments |
| `$#` | number of arguments |
| `$@` | all arguments (quote it: `"$@"`) |
| `$?` | exit status of the last command (0 = success) |
| `$$` | PID of the current shell |
| `$!` | PID of the last background job |

## Exit codes and chaining

```bash
mkdir backup && cp *.txt backup/   # run the second only if the first succeeds
ping -c1 host || echo "host down"  # run the second only if the first fails
grep -q root /etc/passwd
if [[ $? -eq 0 ]]; then echo "found"; fi
```

A safer script header that stops on errors, undefined variables, and failures inside pipes:

```bash
#!/usr/bin/env bash
set -euo pipefail
```

## File test operators

| Test | True when |
|---|---|
| `-e path` | exists |
| `-f path` | regular file |
| `-d path` | directory |
| `-r / -w / -x path` | readable / writable / executable |
| `-s path` | size greater than zero |
| `-z "$str"` / `-n "$str"` | string empty / not empty |

```bash
if [[ -f /etc/passwd ]]; then echo "exists"; fi
```

## Arrays

```bash
tools=("nmap" "gobuster" "ffuf")
echo "${tools[0]}"        # first element
echo "${tools[@]}"        # all elements
echo "${#tools[@]}"       # length
tools+=("sqlmap")         # append
for t in "${tools[@]}"; do echo "$t"; done
```

## Redirection and pipes

| Syntax | Effect |
|---|---|
| `cmd > file` | stdout to file (overwrite) |
| `cmd >> file` | stdout to file (append) |
| `cmd 2> file` | stderr to file |
| `cmd > file 2>&1` or `cmd &> file` | stdout and stderr to file |
| `cmd < file` | file as stdin |
| `cmd1 \| cmd2` | stdout of cmd1 becomes stdin of cmd2 |
| `cmd 2>/dev/null` | discard errors |

## Text-processing toolbox

```bash
grep -i "failed password" /var/log/auth.log       # search (-i ignore case, -r recursive, -v invert)
cut -d: -f1 /etc/passwd                            # field 1, ':' delimiter
awk '{print $1}' access.log                        # first column
sed 's/http:/https:/g' urls.txt                    # find/replace
sort | uniq -c | sort -nr                          # count and rank duplicates
# Top 10 IPs hitting a web server:
awk '{print $1}' access.log | sort | uniq -c | sort -nr | head -10
```

## Scheduling with cron

`crontab -e` edits your jobs. Format: `minute hour day-of-month month day-of-week command`.

```text
0 2 * * *   /home/yahia/backup.sh          # every day at 02:00
*/15 * * * * /home/yahia/check.sh          # every 15 minutes
0 9 * * 1-5 /home/yahia/report.sh          # 09:00 Monday-Friday
```

Security angle: world-writable scripts run by root's cron are a classic Linux privilege-escalation path. Check `/etc/crontab` and `/etc/cron.*` during enumeration.
