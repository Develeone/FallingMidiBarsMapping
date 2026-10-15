#!/bin/zsh
cd "${0:A:h}"
launchctl remove local.falling-bars-midi 2>/dev/null
for attempt in {1..50}; do
    launchctl list local.falling-bars-midi >/dev/null 2>&1 || break
    sleep 0.1
done
launchctl submit -l local.falling-bars-midi -o "$PWD/launcher.log" -e "$PWD/launcher.log" -- "$PWD/.venv312/bin/python" -u "$PWD/launch.py"
