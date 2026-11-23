THE SHEPHERD'S PASTURE
======================

START ON WINDOWS
----------------
1. Extract the entire ZIP file to a normal folder.
2. Double-click run_game.bat.
3. Your browser opens the game. Keep the black Python server window open.

DEPENDENCIES
------------
The game uses Python's standard library only. It does not need Streamlit,
Pygame, FastAPI, Flask, Node.js, or any pip packages. There is no requirements
file to install; no `pip install` command is needed.

Python 3.9 or newer is still required to run the Python backend. If Python
is already installed on your PC, the launcher finds it automatically.

MOBILE PLAY
-----------
The game has touch controls and a responsive full-screen layout. To play on a
phone or tablet, start the game on a computer connected to the same Wi-Fi,
then open the LAN address printed in the Python server window. Keep the server
running while the phone is connected. The game is not a native Android APK.

CONTROLS
--------
WASD / Arrow Keys : Move
Haunted Tree       : Touch it three times to enter Sheol
C                  : Open / close the manuscript
F1                 : Open / close the developer console
R                  : Restart after an ending
Fullscreen button : Toggle fullscreen

MOBILE
------
Use the on-screen directional pad. The book button opens the manuscript.

DEVELOPER CONSOLE
-----------------
Type `help` in the console for available commands. Supported commands:
help, reset, revive, crown, abyss, trueabyss, unlockall, godmode,
speed <number>, teleport, clear.

GAME / TECHNICAL NOTES
---------------------
- Python owns the game state, movement, collisions, fruit/seal progression,
  realm transitions, stalker AI, jumpscare timing, and endings.
- The HTML canvas is the visual/input layer. It uses no external JS library.
- Supplied sprites are stored in `assets/` and referenced by their filenames.
- The stalker hides behind nearby trees, stalks outside the light, and triggers a jumpscare when the sheep approaches either the monster or its hiding tree.
- The Abyss and Bottomless Pit use a limited circular light radius. Tree canopies and trunks cast darkness that blocks the light.
- Dimension-transition, proximity, collection, and jumpscare sounds are
  synthesized locally with Web Audio; no online audio files are used.
- Save progress is written to save.json in this folder.

ADDING MORE SPRITES
-------------------
Place additional PNG files in `assets/`, then add the exact filename to the
`assetFiles` list in index.html and use that filename in the renderer. All
provided sprites, including `Haunted Tree.png`, are stored in this folder.

TROUBLESHOOTING
---------------
- If the page cannot connect, check that the Python server window is still
  open and refresh http://127.0.0.1:8765.
- If Windows Firewall asks about the local server, allow access on Private
  networks if you intend to connect from your own phone/tablet.
- If the browser is silent, click ENTER THE PASTURE once to enable audio.
- The game must be opened through run_game.bat; opening index.html directly
  will not start the Python game engine.
