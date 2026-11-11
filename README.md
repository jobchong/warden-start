# Warden Start

For the English GOG release of Dragon Age: Origins – Ultimate Edition (1.05) with Awakening installed.

Choose **New Game → Dragon Age: Origins**, create your Warden and finish the opening scene. Use the normal level-up screen to spend your points. The Origins build uses Awakening’s level-35 XP threshold of 353,501. A wooden chest beside the starting waypoint contains the Origins, enabled Origins DLC and Awakening item templates. There is another copy of the supply chest by the party camp entrance. Each chest has its own inventory. Pick out the gear you want. Quest keys, story objects and internal variants are also in the list, so taking everything can affect quest progression.

The Origins chest includes the Sentinel and Hirol’s Defense sets, Voice of Velvet, the Heartwood weapons and the Vigilance crafting variants. Normal class, strength and dexterity requirements apply. DLC campaigns have separate inventories for the resources each campaign loads. Awakening’s chest is at the Vigil’s Keep approach. The standalone hooks target the opening market in Leliana’s Song, Denerim gates in Darkspawn Chronicles, the smithy in Golems of Amgarrak, Flemeth’s hut exterior in Witch Hunt, and Tapster’s Tavern in A Tale of Orzammar.

Scaling uses Origins’ normal calculation with higher area caps and the appearance ceiling lifted. Boss ranks, one-hit encounters, and scripted encounters retain their special rules. Newly spawned creatures can also scale in existing saves while the package is enabled. Existing save files retain the levels of creatures already instantiated.

## Install or remove

The installed mod is the **FereldenWardenStart** folder under Documents/BioWare/Dragon Age/packages/core/override. Close the game before changing the package. To disable it, move that folder outside override. For a stock playthrough use a save from before the mod or create a fresh character. Spent points and items already taken are part of that save.

To rebuild from the installed game, run `python build.py` in this folder. The builder reads the GOG install and enabled add-in list and creates **Package**. It also creates the English item text, equipment models and progression tables from your copy of Awakening. Copy the contents of Package into FereldenWardenStart to reinstall. Supply `--game` or `--profile` for non-default paths. Keep the generated game assets for personal use.

## Console fallback

If an area hook is unavailable, launch DAOrigins.exe with `-enabledeveloperconsole`. Press the console key (grave accent on this profile), type the command and press Enter. The stock console may be invisible. Use `runscript ws_dao` for Origins, `runscript ws_ep1` for Awakening, or `runscript ws_lel`, `ws_drk`, `ws_gib`, `ws_str` or `ws_pcg` with the same runscript prefix in the corresponding standalone campaign. These commands summon that campaign’s chest beside your character if a chest with that tag is absent in the loaded area list. The XP-only command is `runscript ws_grant_xp`.
