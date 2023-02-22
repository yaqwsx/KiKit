## KiKit Symbol and Footprint Libraries

From v6 onwards KiCad comes with a "Plugin and Content Manager" (PCM) which can be used to
add the KiKit symbol and footprint libraries used in multi-board workflows.  The PCM is new
functionality for KiCad though, and only does part of the installation in v6.  To install
the libraries using the PCM:

1. Open KiCad
2. Open the `Tools` menu and select `Plugin and Content Manager`
3. Select the `Libraries` tab and scroll down to `KiKit Library`
4. Press `Install` and then `Apply Changes`
5. Close the Plugin and Content Manager

*The following steps are only required in KiCad 6, they are automated in KiCad 7*:

7. Back in the main KiCad window, open the `Preferences` menu and select `Manage Symbol Libraries`
8. Select the `Global Libraries` tab, and click the `+` icon towards the bottom of the window then
enter `kikit` (all lowercase) as the nickname, and
`${KICAD6_3RD_PARTY}/symbols/com_github_yaqwsx_kikit-library/kikit.kicad_sym` as the Library Path.
8. Press `OK`
9. Back in the main KiCad window, open the `Preferences` menu and select `Manage Footprint Libraries`
10. As before, add a row to the table in the `Global Libraries` tab, with a nickname `kikit` (all
lowercase again), and this time enter
`${KICAD6_3RD_PARTY}/footprints/com_github_yaqwsx_kikit-library/kikit.pretty` for the Library Path.
11. Press `OK`
12. From now on, you can find the KiKit symbols and footprints under `kikit` alongside all the
others.
