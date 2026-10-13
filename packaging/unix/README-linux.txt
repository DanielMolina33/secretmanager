SecretManager for Linux
=======================

Keep the extracted linux directory together. It contains the application under
app/ and this README and configure_launcher.sh at its root. The application
uses its bundled runtime and libraries.

Start the application
---------------------

Open app/SecretManager/SecretManager from your file manager. A terminal is not
needed to start the application.

Add SecretManager to the applications menu
------------------------------------------

The optional configure_launcher.sh script registers SecretManager in your
desktop environment's applications menu. It creates one .desktop entry in:

    ${XDG_DATA_HOME:-$HOME/.local/share}/applications

The entry points to the executable and icon in this extracted linux directory.
It does not copy the application or vault into your home directory.

To run the script:

1. Open the extracted linux directory. It is the directory containing this
   README, configure_launcher.sh, and the app/ folder.
2. Open a terminal in that directory. In a file manager, right-click an empty
   area and choose "Open in Terminal" if available. Otherwise, open a terminal
   and navigate to that directory with `cd`.
3. Run:

       ./configure_launcher.sh

   If the shell reports that permission is denied, run:

       bash ./configure_launcher.sh

4. Search for SecretManager in the desktop environment's applications menu.

If you move the extracted linux directory or its USB mount location changes,
run the script again from its new location. This updates the menu entry to the
new path.

Remove the applications menu entry
-----------------------------------

Open a terminal in the same extracted linux directory and run:

    ./configure_launcher.sh --remove

If permission is denied, run:

    bash ./configure_launcher.sh --remove

This removes the menu entry only. It does not delete the application, vault, or
other files in the portable directory. Running the script from a file manager
may not show its output; use a terminal for these steps.

The ELF executable may have a generic icon in the file manager. The registered
.desktop entry provides the SecretManager icon in the applications menu and
allows the desktop environment to associate the running window with it.
