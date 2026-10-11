# Third-party tools

Fetched locally, git-ignored, not redistributed.

| Folder | Source | Version | License | Used for |
|---|---|---|---|---|
| `fli_save_editor\` | https://github.com/Niedzielan/fli_save_editor | commit `124135c6dd520afbd7af541ccf390478e52b9008` (2026-08-27, "2.2.0 fix") | none published (personal use only) | `fli_sav_pattern.txt` save layout, `fli_sav2json.py` parser, `itemlist.txt` names |
| `ue4ss\` | https://github.com/UE4SS-RE/RE-UE4SS/releases/tag/experimental-latest | `UE4SS_v3.0.1-1164-g5e627997.zip`, SHA-256 `3C72142A383E25E9F9553AC9E4D5677AA572E98CB369CAC57200EFB2E381E603` | MIT (`dist\ue4ss\LICENSE`) | Mode B runtime (reflection + game-thread execution) |

Re-fetch:

```powershell
git clone https://github.com/Niedzielan/fli_save_editor.git tools\fli_save_editor; git -C tools\fli_save_editor checkout 124135c6dd520afbd7af541ccf390478e52b9008
Invoke-WebRequest https://github.com/UE4SS-RE/RE-UE4SS/releases/download/experimental-latest/UE4SS_v3.0.1-1164-g5e627997.zip -OutFile tools\ue4ss\UE4SS_v3.0.1-1164-g5e627997.zip
Expand-Archive tools\ue4ss\UE4SS_v3.0.1-1164-g5e627997.zip tools\ue4ss\dist
```
