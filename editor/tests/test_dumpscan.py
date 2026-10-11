from stolenhours import dumpscan

DUMP = """# StolenHours value dump
=== DP1GameInstance /Engine/Transient.DP1GameInstance_0
  -- Class /Script/DP1Project.DP1GameInstance
  0x0310 IntProperty CurrentMoney = 14633
  0x0314 IntProperty NotMoney = 146330
  0x0320 StrProperty PlayerName = "N30Killer"
  0x0330 StructProperty Status = {Lv=11, Exp=221, Money=14633}
=== Widget /Game/UI/WBP_Hud.WBP_Hud_C_0
  -- WidgetBlueprintGeneratedClass /Game/UI/WBP_Hud.WBP_Hud_C
  0x0400 TextProperty MoneyText = "14,633"
  0x0408 FloatProperty Ratio = 14633.5
"""


def test_analyze_finds_exact_values(tmp_path):
    f = tmp_path / "values_1.txt"
    f.write_text(DUMP, encoding="utf-8")
    targets = {"Money": 14633, "character name": "N30Killer", "life0000 level": 11}
    rep = dumpscan.analyze(f, targets)
    assert rep.objects == 2 and rep.props == 6
    assert [p.name for p in rep.hits["Money"]] == ["CurrentMoney", "Status"]
    assert rep.hits["Money"][0].offset == 0x310
    assert [p.name for p in rep.hits["character name"]] == ["PlayerName"]
    assert [p.name for p in rep.hits["life0000 level"]] == ["Status"]
    assert {p.name for p in rep.interesting} >= {"CurrentMoney", "PlayerName", "Status"}
    text = dumpscan.format_report(rep, targets)
    assert "CurrentMoney @0x310" in text
