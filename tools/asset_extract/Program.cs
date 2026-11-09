// Read-only asset extractor for the editor's look: lists packaged files and exports textures as PNG.
// usage: asset_extract <paksDir> <aesKeyHex> <mappings.usmap> list <regex>
//        asset_extract <paksDir> <aesKeyHex> <mappings.usmap> export <regex> <outDir>   (textures -> PNG)
//        asset_extract <paksDir> <aesKeyHex> <mappings.usmap> raw <regex> <outDir>      (file bytes as packaged)
//        asset_extract <paksDir> <aesKeyHex> <mappings.usmap> json <regex> <outDir>     (asset exports as JSON)
//        asset_extract <paksDir> <aesKeyHex> <mappings.usmap> mesh <regex> <outDir>     (meshes -> glTF + materials)
//        asset_extract <paksDir> <aesKeyHex> <mappings.usmap> world <regex> <outDir>    (UWorld -> USD + streaming meshes)
//        asset_extract <paksDir> <aesKeyHex> <mappings.usmap> anim <regex> <outDir>     (anim sequences -> per-frame local
//                                                                                        bone transforms, UE space, JSON)
using System.Text.RegularExpressions;
using CUE4Parse.Compression;
using CUE4Parse.Encryption.Aes;
using CUE4Parse.FileProvider;
using CUE4Parse.MappingsProvider.Usmap;
using CUE4Parse_Conversion.Options;
using CUE4Parse.UE4.Assets.Exports.Texture;
using CUE4Parse.UE4.Objects.Core.Misc;
using CUE4Parse.UE4.Objects.Engine;
using CUE4Parse.UE4.Versions;
using CUE4Parse_Conversion.Exporters;
using CUE4Parse_Conversion.Textures;
using CUE4Parse_Conversion;

if (args.Length < 5) { Console.Error.WriteLine("see header comment for usage"); return 2; }
var (paks, key, usmap, mode, pattern) = (args[0], args[1], args[2], args[3], new Regex(args[4], RegexOptions.IgnoreCase));

var oodle = Path.Combine(AppContext.BaseDirectory, OodleHelper.OODLE_NAME_CURRENT);
if (!File.Exists(oodle)) await OodleHelper.DownloadOodleDllAsync(ref oodle, CancellationToken.None);
OodleHelper.Initialize(oodle);

var provider = new DefaultFileProvider(paks, SearchOption.TopDirectoryOnly, new VersionContainer(EGame.GAME_UE5_4));
provider.MappingsContainer = new FileUsmapTypeMappingsProvider(usmap, StringComparer.OrdinalIgnoreCase);
provider.ReadScriptData = mode == "json";  // Blueprint function bytecode in the JSON (widget logic, e.g. which material an icon gets)
provider.Initialize();
provider.SubmitKey(new FGuid(), new FAesKey(key.StartsWith("0x") ? key : "0x" + key));
provider.PostMount();

var matches = provider.Files.Keys.Where(p => pattern.IsMatch(p)).OrderBy(p => p).ToList();
if (mode == "list")
{
    foreach (var p in matches) Console.WriteLine(p);
    Console.Error.WriteLine($"{matches.Count} of {provider.Files.Count} files");
    return 0;
}

var outDir = args[5];
if (mode == "raw")
{
    foreach (var p in matches)
    {
        var target = Path.Combine(outDir, p);
        Directory.CreateDirectory(Path.GetDirectoryName(target)!);
        File.WriteAllBytes(target, provider.SaveAsset(p));
        Console.WriteLine(p);
    }
    return 0;
}
if (mode == "json")
{
    foreach (var p in matches.Where(p => p.EndsWith(".uasset")))
    {
        var target = Path.Combine(outDir, Path.ChangeExtension(p, ".json"));
        Directory.CreateDirectory(Path.GetDirectoryName(target)!);
        File.WriteAllText(target, Newtonsoft.Json.JsonConvert.SerializeObject(provider.LoadPackage(p).GetExports(), Newtonsoft.Json.Formatting.Indented));
        Console.WriteLine(p);
    }
    return 0;
}
TextureDecoder.UseAssetRipperTextureDecoder = true;
if (mode == "mesh" || mode == "world")
{
    var meshFmt = mode == "world" ? EMeshFormat.USD : EMeshFormat.Gltf2;
    var options = new ExportOptions(meshFormat: meshFmt, exportMorphTargets: false, socketFormat: ESocketFormat.None);
    var session = new ExportSession(null);
    var pkgs = matches.Where(p => mode == "world" ? p.EndsWith(".umap") : p.EndsWith(".uasset"));
    foreach (var p in pkgs)
    {
        try
        {
            foreach (var obj in provider.LoadPackage(p).GetExports())
            {
                if (mode == "world" && obj is UWorld world)
                    session.Add(new WorldExporter(world));
                else if (mode == "mesh" && obj is CUE4Parse.UE4.Assets.Exports.SkeletalMesh.USkeletalMesh
                         or CUE4Parse.UE4.Assets.Exports.StaticMesh.UStaticMesh)
                    session.Add(obj);
            }
        }
        catch (Exception e) { Console.Error.WriteLine($"{p}: {e.Message}"); }
    }
    var results = await session.RunAsync(outDir, options, null, CancellationToken.None);
    int n = 0, bad = 0;
    foreach (var r in results)
    {
        if (r.Success) { n++; foreach (var f in r.DiskFilePaths) Console.WriteLine(f); }
        else { bad++; Console.Error.WriteLine($"{r.ObjectPath}: {r.Error?.Message}"); }
    }
    Console.WriteLine($"exported {n} objects, {bad} failed");
    return 0;
}
if (mode == "anim")
{
    foreach (var p in matches.Where(p => p.EndsWith(".uasset")))
    {
        try
        {
            foreach (var obj in provider.LoadPackage(p).GetExports())
            {
                if (obj is not CUE4Parse.UE4.Assets.Exports.Animation.UAnimSequence seq) continue;
                var skel = seq.Skeleton.Load<CUE4Parse.UE4.Assets.Exports.Animation.USkeleton>()!;
                var set = CUE4Parse_Conversion.Animations.AnimConverter.ConvertAnims(skel, seq);
                var info = skel.ReferenceSkeleton.FinalRefBoneInfo;
                var refPose = skel.ReferenceSkeleton.FinalRefBonePose;
                foreach (var s in set.Sequences)
                {
                    var bones = new List<object>();
                    for (int b = 0; b < s.Tracks.Count && b < info.Length; b++)
                    {
                        var t = s.Tracks[b];
                        var pos = new List<float[]>(); var rot = new List<float[]>(); var scl = new List<float[]>();
                        var rp = refPose[b];
                        for (int f = 0; f < s.NumFrames; f++)
                        {
                            pos.Add(Sample(t.KeyPos.Select(v => new[] { v.X, v.Y, v.Z }).ToArray(), Times(t.KeyPosTime, t.KeyTime), f,
                                new[] { rp.Translation.X, rp.Translation.Y, rp.Translation.Z }));
                            rot.Add(Sample(t.KeyQuat.Select(v => new[] { v.X, v.Y, v.Z, v.W }).ToArray(), Times(t.KeyQuatTime, t.KeyTime), f,
                                new[] { rp.Rotation.X, rp.Rotation.Y, rp.Rotation.Z, rp.Rotation.W }, true));
                            scl.Add(Sample(t.KeyScale.Select(v => new[] { v.X, v.Y, v.Z }).ToArray(), Times(t.KeyScaleTime, t.KeyTime), f,
                                new[] { rp.Scale3D.X, rp.Scale3D.Y, rp.Scale3D.Z }));
                        }
                        bones.Add(new { name = info[b].Name.Text, parent = info[b].ParentIndex,
                            refPos = new[] { rp.Translation.X, rp.Translation.Y, rp.Translation.Z },
                            refRot = new[] { rp.Rotation.X, rp.Rotation.Y, rp.Rotation.Z, rp.Rotation.W },
                            pos, rot, scl });
                    }
                    var target = Path.Combine(outDir, Path.ChangeExtension(p, null) + ".anim.json");
                    Directory.CreateDirectory(Path.GetDirectoryName(target)!);
                    File.WriteAllText(target, Newtonsoft.Json.JsonConvert.SerializeObject(new { name = s.Name, fps = s.FramesPerSecond, frames = s.NumFrames, bones }));
                    Console.WriteLine(target);
                }
            }
        }
        catch (Exception e) { Console.Error.WriteLine($"{p}: {e}"); }
    }
    return 0;
}
int ok = 0, fail = 0;
foreach (var p in matches.Where(p => p.EndsWith(".uasset")))
{
    try
    {
        foreach (var obj in provider.LoadPackage(p).GetExports())
        {
            if (obj is not UTexture2D tex) continue;
            var decoded = tex.Decode(ETexturePlatform.DesktopMobile);
            if (decoded is null) continue;
            var target = Path.Combine(outDir, Path.ChangeExtension(p, null) + ".png");
            Directory.CreateDirectory(Path.GetDirectoryName(target)!);
            File.WriteAllBytes(target, decoded.Encode(ETextureFormat.Png, false, out _));
            ok++;
        }
    }
    catch (Exception e) { fail++; Console.Error.WriteLine($"{p}: {e.Message}"); }
}
Console.WriteLine($"exported {ok} textures, {fail} failed");
return 0;

// Key arrays carry their own times (in frames), share KeyTime, or have one key per frame / one constant key.
static float[]? Times(float[]? own, float[]? shared) => own is { Length: > 0 } ? own : shared is { Length: > 0 } ? shared : null;

static float[] Sample(float[][] keys, float[]? times, int frame, float[] fallback, bool quat = false)
{
    if (keys.Length == 0) return fallback;
    if (keys.Length == 1) return keys[0];
    if (times is null || times.Length != keys.Length) return keys[Math.Min(frame, keys.Length - 1)];
    int i = 0;
    while (i < times.Length - 1 && times[i + 1] <= frame) i++;
    if (i >= times.Length - 1 || frame <= times[i]) return keys[i];
    float a = (frame - times[i]) / (times[i + 1] - times[i]);
    var (k0, k1) = (keys[i], keys[i + 1]);
    float sign = 1;
    if (quat && k0.Zip(k1, (x, y) => x * y).Sum() < 0) sign = -1;
    var r = k0.Select((x, j) => x + (sign * k1[j] - x) * a).ToArray();
    if (quat) { var n = MathF.Sqrt(r.Sum(x => x * x)); r = r.Select(x => x / n).ToArray(); }
    return r;
}
