# Let It Die Launcher Manager
<p align="center">
<img width="256" height="256" alt="Lidico" src="https://github.com/user-attachments/assets/4c916afc-a987-4f24-9c13-573cb9c63348" />
</p>
<img width="1031" height="548" alt="image" src="https://github.com/user-attachments/assets/eadfa9e0-c2ff-49fe-a39b-d0af8bd59abe" />

Launches a stack of executables when this program starts.
Each block is one .exe. Only checkboxed blocks are launched.
If an exe is already running, it is skipped.

## How it works

```
1. Start the program.
2. Optionally fill the fixed top block. Browse asks for steam.exe
   and fills:
   SteamFolder\steamapps\common\LET IT DIE\Binaries\Win64\BrgGame-Steam.exe
3. Click + to add more blocks. Browse to an .exe.
4. Tick a block to make it active. Arrows set launch order.
   The top of the list launches first.
5. Click Save EXEs. On later starts, active blocks launch on countdown
   unless Disable self-launch is ticked.
```

## Fixed top block

```
Labelled steam.exe. Always first. Cannot be deleted or reordered.
Empty path is ignored. Close all does not touch it.
The X clears the path instead of removing the block.
```

## Buttons

```
+                  add a block
Browse             pick an .exe
▲ / ▼              move a normal block. top launches first
✕                  remove that block (fixed block: clear the path)
Save EXEs          write the list to EXEs.json
Open all active    launch every checked block that is not already running
Close all          close running exes from normal blocks only
Close              exit this program
Create shortcut    desktop shortcut. uses Swap_App_Thumbnail image if set
```

## Start

```
grace_time = 3
    countdown before the stack launches.
    Cancel launch stack skips the stack and opens this program.
    0 skips the countdown.
    still shows when start_minimized is true and this is not set to 0.

wait_between_launches = 3
    seconds between each exe. under 1 becomes 1. decimals round up.

Disable self-launch
    no stack on start, no countdown. Open all active button still works.

start_minimized = true
    ini only. main window starts hidden. countdown still shows
    if grace_time is greater than 0.
```

## Hide / show

```
Default hotkey is -
Press to hide. Press again to show. Works while hidden.
Click the Hide UI label to set another key.
disable_shortcut = true turns shortcut action off.
Launching the exe or the shortcut again closes this program
and starts the new one. It does not close the other programs.
```

## Files

```
settings.ini          hotkey, start_minimized, grace_time,
                      disable_shortcut, wait_between_launches,
                      Swap_App_Thumbnail, disable_self_launch
EXEs.json             the block list. Save EXEs overwrites it.
execute.lock          while running. relaunch closes the old one.
Swap_App_Thumbnail    full path to an .ico (png is converted).
                      quotes, spaces, and mixed slashes are ignored.
                      empty keeps Lidico.
UI_Assets             UI background.webp
                      let it die cursor.webp
                      uncle glasses ready.webp
                      Lidico.webp
                      Lidico.ico
```

## License and disclaimer

```
This is an unofficial fan tool with fanmade assets. It is not affiliated with, authorized,
or endorsed by Grasshopper Manufacture or GungHo Online Entertainment.
LET IT DIE, its characters, names, and setting remain their property.
```

## Other helpful programs

- [Let It Die Borderless](https://github.com/Grimfuldev/let_it_die_borderless)
- [Let It Die Launcher Manager](https://github.com/Grimfuldev/let_it_die_launcher_manager)
- [Let It Die Local Saver](https://github.com/Grimfuldev/Let_it_Die_Local_Saver)
- [Let It Die Seasons and Rotations Changer](https://github.com/Grimfuldev/let_it_die_rotations_and_seasons)
