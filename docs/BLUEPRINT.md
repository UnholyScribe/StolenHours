# Blueprint (as received from Unholy, 2026-10-11)

Saved verbatim. This is the brief, **not verified fact**: several parts already disagree with the real game.
Check `FINDINGS.md` before relying on any constant, path, key or layout below.

```text
# ==============================================================================
# FANTASY LIFE i: THE GIRL WHO STEALS TIME
# COMPLETE HYBRID SAVE EDITOR & LIVE RUNTIME CONTROLLER SPECIFICATION
# ==============================================================================

# ==============================================================================
# SECTION 1: TARGET ARTIFACTS & FILE DIRECTORIES
# ==============================================================================

Steam App ID: 2993780
Save Directory: C:\Program Files (x86)\Steam\userdata\<Steam3ID>\2993780\remote\

Target Save Artifacts:
  - 002DAE74-00-gamedata.bin   : Active character state, inventory array, world 
                                 progression flags, island layouts, NPC data.
  - 002DAE74-00-systemdata.bin : Engine display/sound preferences, Steam account 
                                 binding, achievement unlock bits.

Game Binary Location:
  - <SteamLibrary>\steamapps\common\FANTASY LIFE i The Girl Who Steals Time\FLiGame\Binaries\Win64\FLiGame-Win64-Shipping.exe


# ==============================================================================
# SECTION 2: BINARY CONTAINER & CRYPTOGRAPHIC PIPELINE
# ==============================================================================

Level-5 wraps the raw serialized Unreal Engine 5 GVAS stream inside a custom 
3-layer proprietary cryptographic container.

CONTAINER HEADER LAYOUT (64 Bytes Total):
+--------+------+------------+-------------------------------------------------+
| Offset | Size | Type       | Identifier & Description                        |
+--------+------+------------+-------------------------------------------------+
| 0x00   | 0x04 | char[4]    | Magic identifier: "L5SV" (0x4C355356)           |
| 0x04   | 0x20 | uint8[32]  | Seed_dyn: Dynamic 32-byte cryptographic seed    |
| 0x24   | 0x04 | uint32_le  | Decompressed GVAS payload size (bytes)          |
| 0x28   | 0x04 | uint32_le  | Encrypted payload length (bytes)                |
| 0x2C   | 0x14 | uint8[20]  | Reserved / SHA-256 payload integrity block      |
+--------+------+------------+-------------------------------------------------+
| 0x40   | ...  | uint8[]    | Ciphertext payload (Length = EncryptedSize)     |
+--------+------+------------+-------------------------------------------------+

DECONTAINERIZATION PIPELINE (DISASSEMBLY FLOW):
  1. Header Parse: Extract Magic, Seed_dyn, DecompressedSize, EncryptedSize.
  2. Layer 1 (Decoy XOR): Apply cyclic 4-byte XOR using key 0xF18F6AA4 
     (Little-Endian byte sequence: [0xA4, 0x6A, 0x8F, 0xF1]) starting at 0x40.
  3. Layer 2 (AES-128-ECB): Decrypt L1 output using static 16-byte key extracted 
     from game shipping binary. Requires 16-byte block alignment (PKCS#7).
  4. Layer 3 (Dynamic Stream XOR): Expand Seed_dyn into an incrementing counter 
     keystream using AES-256-ECB. XOR byte-for-byte against Layer 2 output.
  5. Decompression: If DecompressedSize > EncryptedSize, feed payload to Oodle 
     Kraken decompressor (OodleLZ_Decompress via ooz or liboodle.dll).


# ==============================================================================
# SECTION 3: UNREAL ENGINE 5 GVAS BINARY SERIALIZATION SPECIFICATION
# ==============================================================================

GVAS HEADER STRUCTURE (Raw Decompressed Stream):
  - Offset 0x00: char[4] Magic ('GVAS' / 0x53415647)
  - Offset 0x04: uint32 SaveGameFileVersion (UE Save Version, typically 2 or 3)
  - Offset 0x08: uint32 PackageFileVersionUE5 (522 for UE 5.4)
  - Offset 0x0C: uint16 EngineVersionMajor (5)
  - Offset 0x0E: uint16 EngineVersionMinor (4)
  - Offset 0x10: FString CustomSaveClassName ("/Script/FLiGame.FLiSaveGameInstance")

STRING (FString) SERIALIZATION FORMAT:
  - int32 Length Prefix (N)
    * If N > 0 : UTF-8 encoded string of length N (includes null terminator \0).
    * If N < 0 : UTF-16-LE encoded string of length |N| characters (2 * |N| bytes).
    * If N == 0: Empty string.

TAGGED PROPERTY BINARY LAYOUT:
  [PropertyName: FString]
  [PropertyType: FString]
  [PayloadSize: uint32_le]
  [ArrayIndex: uint32_le]
  [TypeSpecificMetadata]
  [PropertyPayloadBytes: PayloadSize bytes]

TARGET PROPERTY MAPPINGS:
  1. CharacterData (StructProperty):
     - Dosh             -> Int64Property (Direct 8-byte signed integer)
     - CurrentLife      -> ByteProperty / EnumProperty (e.g. ELifeType::Miner)
     - LifeStats        -> MapProperty (Key: ELifeType, Value: FLifeProgress)
     - StatusAttributes -> StructProperty (Allocated STR, VIT, INT, FOC, DEX)
  2. InventoryData (StructProperty):
     - Items            -> ArrayProperty of StructProperty (FInventorySlot)
                           Sub-fields: ItemID (FName), Quantity (Int32), 
                                       Quality (Byte), TraitIDs (ArrayProperty)
  3. AppearanceData (StructProperty):
     - MeshAssets       -> ArrayProperty of FName (Skeletal mesh identifiers)
     - ColorParameters  -> ArrayProperty of FLinearColor (4x float32: R, G, B, A 
                           scaled 0.0 to 1.0)
  4. Block Termination:
     - All nested StructProperty and Object hierarchies terminate on FName "None"
       Binary: 0x05 0x00 0x00 0x00 0x4E 0x6F 0x6E 0x65 0x00 ("None\0").


# ==============================================================================
# SECTION 4: PYTHON OFFLINE SAVE UNPACKER & PACKER IMPLEMENTATION
# ==============================================================================

import os
import struct
from Crypto.Cipher import AES

# Optional: import ooz (for Kraken compression)

class FLiSavePipeline:
    MAGIC = b"L5SV"
    XOR_KEY = b"\xa4\x6a\x8f\xf1"  # 0xF18F6AA4 Little-Endian
    STATIC_AES_KEY = b"REPLACE_WITH_EXTRACTED_16B_KEY"

    def __init__(self):
        pass

    def _derive_keystream(self, seed: bytes, length: int) -> bytes:
        stream = bytearray()
        counter = 0
        cipher = AES.new(seed, AES.MODE_ECB)
        while len(stream) < length:
            block = cipher.encrypt(counter.to_bytes(16, byteorder="little"))
            stream.extend(block)
            counter += 1
        return bytes(stream[:length])

    def unpack(self, raw_data: bytes) -> bytes:
        # 1. Parse Container Header
        if raw_data[:4] != self.MAGIC:
            raise ValueError("Invalid magic identifier. Expected L5SV.")

        seed_dyn = raw_data[4:36]
        decomp_size = struct.unpack("<I", raw_data[36:40])[0]
        enc_size = struct.unpack("<I", raw_data[40:44])[0]
        payload = bytearray(raw_data[64:64 + enc_size])

        # 2. Layer 1: Decoy Cyclic XOR Deshuffle
        for i in range(len(payload)):
            payload[i] ^= self.XOR_KEY[i % 4]

        # 3. Layer 2: AES-128-ECB Decryption
        cipher_l2 = AES.new(self.STATIC_AES_KEY, AES.MODE_ECB)
        decrypted_l2 = cipher_l2.decrypt(bytes(payload))

        # 4. Layer 3: Dynamic Keystream XOR
        keystream = self._derive_keystream(seed_dyn, len(decrypted_l2))
        decomp_target = bytearray(len(decrypted_l2))
        for i in range(len(decrypted_l2)):
            decomp_target[i] = decrypted_l2[i] ^ keystream[i]

        # 5. Decompression Check
        if decomp_size > len(decomp_target):
            # return ooz.decompress(bytes(decomp_target), decomp_size)
            raise NotImplementedError("Link liboodle/ooz to decompress Kraken stream.")

        return bytes(decomp_target[:decomp_size])

    def pack(self, gvas_bytes: bytes) -> bytes:
        decomp_size = len(gvas_bytes)

        # 1. Compression (Pass raw if uncompressed flag configured)
        # comp_data = ooz.compress(gvas_bytes)
        comp_data = gvas_bytes

        # PKCS#7 / 16-byte Block Padding for AES-ECB
        pad_len = 16 - (len(comp_data) % 16)
        if pad_len != 16:
            comp_data += bytes([pad_len] * pad_len)

        enc_size = len(comp_data)
        seed_dyn = os.urandom(32)

        # 2. Layer 3: Dynamic Keystream XOR
        keystream = self._derive_keystream(seed_dyn, enc_size)
        l3_out = bytearray(enc_size)
        for i in range(enc_size):
            l3_out[i] = comp_data[i] ^ keystream[i]

        # 3. Layer 2: AES-128-ECB Encryption
        cipher_l2 = AES.new(self.STATIC_AES_KEY, AES.MODE_ECB)
        l2_out = cipher_l2.encrypt(bytes(l3_out))

        # 4. Layer 1: Decoy Cyclic XOR
        l1_out = bytearray(l2_out)
        for i in range(len(l1_out)):
            l1_out[i] ^= self.XOR_KEY[i % 4]

        # 5. Build Container Header (64 bytes)
        header = bytearray(64)
        header[0:4] = self.MAGIC
        header[4:36] = seed_dyn
        header[36:40] = struct.pack("<I", decomp_size)
        header[40:44] = struct.pack("<I", enc_size)
        # Bytes 0x2C - 0x3F remain zeroed / padding

        return bytes(header + l1_out)


# ==============================================================================
# SECTION 5: LIVE RUNTIME ARCHITECTURE & THE RAM/DISK SYNCHRONIZATION PROBLEM
# ==============================================================================

SYNCHRONIZATION RISK:
  If a desktop editor writes changes directly to the save file (.bin) on disk 
  while the game process is running, the next in-game auto-save, fast-travel, 
  or scene transition will dump the game's active RAM state directly onto the 
  file, completely overwriting the external modifications.

HYBRID OPERATIONAL MODEL:
  - Mode A (Game Closed): 
      Editor performs direct cryptographic unpacking, property editing, 
      repacking, and disk writes on 002DAE74-00-gamedata.bin.
  - Mode B (Game Running): 
      Editor locks direct file writes. Live UI buttons dispatch real-time 
      packets over a Windows Named Pipe directly to an injected Proxy DLL, 
      manipulating the game state in RAM without disk collisions.

UNREAL ENGINE GAME THREAD BARRIER:
  Directly invoking engine functions (such as AFLiWorldManager::TriggerEvent 
  or SpawnActor) from an asynchronous IPC thread causes immediate fatal access 
  violations (0xC0000005). All world mutations must be queued in an atomic 
  buffer and dispatched strictly within the native Game Thread loop 
  (e.g., inside a hooked UObject::ProcessEvent dispatcher or Engine Tick).


# ==============================================================================
# SECTION 6: IN-GAME PROXY DLL HOOK & NAMED PIPE SERVER (C++)
# ==============================================================================

// Compile as 64-bit DLL: "version.dll" or "dxgi.dll"
// Target Directory: FLiGame/Binaries/Win64/
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <atomic>
#include <string>
#include "MinHook.h" // MinHook x64 API Hooking Engine

// Forwarding pointer for proxying system calls to authentic DLL
HINSTANCE hOriginalDll = NULL;
typedef DWORD(WINAPI* PFN_GetFileVersionInfoSizeW)(LPCWSTR, LPDWORD);
PFN_GetFileVersionInfoSizeW Real_GetFileVersionInfoSizeW = NULL;

extern "C" __declspec(dllexport) DWORD WINAPI GetFileVersionInfoSizeW(LPCWSTR filename, LPDWORD handle) {
    if (!Real_GetFileVersionInfoSizeW) {
        Real_GetFileVersionInfoSizeW = (PFN_GetFileVersionInfoSizeW)GetProcAddress(hOriginalDll, "GetFileVersionInfoSizeW");
    }
    return Real_GetFileVersionInfoSizeW(filename, handle);
}

// -----------------------------------------------------------------------------
// ENGINE TYPES & FUNCTION SIGNATURES
// -----------------------------------------------------------------------------
// typedef void (*tProcessEvent)(void* Object, void* Function, void* Parms);
typedef void (*tProcessEvent)(void* Object, void* Function, void* Parms);
tProcessEvent oProcessEvent = nullptr;

// Thread-safe command queue flags
std::atomic<bool> g_bForceLegendaryQueued(false);
std::atomic<bool> g_bPipeRunning(true);

// -----------------------------------------------------------------------------
// NAMED PIPE SERVER WORKER THREAD
// -----------------------------------------------------------------------------
DWORD WINAPI NamedPipeServerThread(LPVOID lpParam) {
    HANDLE hPipe;
    char buffer[256];
    DWORD dwRead;

    while (g_bPipeRunning) {
        hPipe = CreateNamedPipeA(
            "\\\\.\\pipe\\FLiLiveController",
            PIPE_ACCESS_DUPLEX,
            PIPE_TYPE_MESSAGE | PIPE_READMODE_MESSAGE | PIPE_WAIT,
            1,                  // Max instances
            1024, 1024,         // In/Out buffer sizes
            NMPWAIT_USE_DEFAULT_WAIT,
            NULL
        );

        if (hPipe == INVALID_HANDLE_VALUE) {
            Sleep(1000);
            continue;
        }

        // Await connection from Desktop Save Editor GUI
        BOOL bConnected = ConnectNamedPipe(hPipe, NULL) ? TRUE : (GetLastError() == ERROR_PIPE_CONNECTED);
        if (bConnected) {
            while (ReadFile(hPipe, buffer, sizeof(buffer) - 1, &dwRead, NULL)) {
                buffer[dwRead] = '\0';
                std::string cmd(buffer);

                if (cmd == "FORCE_LEGENDARY_EVENT") {
                    // Queue dispatch for the Game Thread
                    g_bForceLegendaryQueued.store(true);

                    const char* reply = "ACK_QUEUED\n";
                    DWORD dwWritten;
                    WriteFile(hPipe, reply, (DWORD)strlen(reply), &dwWritten, NULL);
                }
            }
        }
        DisconnectNamedPipe(hPipe);
        CloseHandle(hPipe);
    }
    return 0;
}

// -----------------------------------------------------------------------------
// GAME THREAD HOOK DISPATCHER (UObject::ProcessEvent)
// -----------------------------------------------------------------------------
void hkProcessEvent(void* Object, void* Function, void* Parms) {
    // Check if an external action was requested by the GUI
    if (g_bForceLegendaryQueued.load()) {
        // Reset flag immediately to prevent repeat triggers
        g_bForceLegendaryQueued.store(false);

        // Native Game Thread context safely established here.
        // Resolve world managers and invoke spawn functions:
        // Example logic:
        // AFLiWorldManager* WorldMgr = GetWorldManager();
        // if (WorldMgr) {
        //     WorldMgr->ForceSpawnWorldEvent(FName("Event_Legendary_Beast"));
        // }
    }

    // Forward execution to authentic Unreal Engine ProcessEvent
    oProcessEvent(Object, Function, Parms);
}

// -----------------------------------------------------------------------------
// DLL LIFECYCLE & INITIALIZATION
// -----------------------------------------------------------------------------
uintptr_t FindPattern(const char* pattern, const char* mask) {
    // Standard pattern scanner implementation across executable code segments
    return 0; // Replace with memory scanner offset
}

DWORD WINAPI MainThread(LPVOID lpParam) {
    // 1. Link authentic system version.dll from System32
    wchar_t systemPath[MAX_PATH];
    GetSystemDirectoryW(systemPath, MAX_PATH);
    wcscat_s(systemPath, L"\\version.dll");
    hOriginalDll = LoadLibraryW(systemPath);

    // 2. Initialize MinHook Framework
    if (MH_Initialize() != MH_OK) return 1;

    // 3. Scan for UObject::ProcessEvent signature in FLiGame-Win64-Shipping.exe
    // Signature: 40 55 56 57 41 54 41 55 41 56 41 57 48 8D 6C 24 ? 48 81 EC
    uintptr_t pProcessEvent = FindPattern("\x40\x55\x56\x57\x41\x54\x41\x55\x41\x56\x41\x57\x48\x8D\x6C\x24\x00\x48\x81\xEC", "xxxxxxxxxxxxxxxx?xxx");

    if (pProcessEvent) {
        MH_CreateHook((void*)pProcessEvent, &hkProcessEvent, (void**)&oProcessEvent);
        MH_EnableHook((void*)pProcessEvent);
    }

    // 4. Start Named Pipe IPC Server Thread
    CreateThread(NULL, 0, NamedPipeServerThread, NULL, 0, NULL);

    return 0;
}

BOOL APIENTRY DllMain(HMODULE hModule, DWORD ul_reason_for_call, LPVOID lpReserved) {
    if (ul_reason_for_call == DLL_PROCESS_ATTACH) {
        DisableThreadLibraryCalls(hModule);
        CreateThread(NULL, 0, MainThread, NULL, 0, NULL);
    } else if (ul_reason_for_call == DLL_PROCESS_DETACH) {
        g_bPipeRunning.store(false);
        MH_DisableHook(MH_ALL_HOOKS);
        MH_Uninitialize();
    }
    return TRUE;
}


# ==============================================================================
# SECTION 7: DESKTOP SAVE EDITOR CLIENT IPC INTEGRATION (PYTHON)
# ==============================================================================

import win32file
import win32pipe

class FLiLiveBridge:
    PIPE_NAME = r"\\.\pipe\FLiLiveController"

    @classmethod
    def send_command(cls, command: str) -> bool:
        """
        Transmits real-time control command to the running in-game DLL hook.
        Returns True if command was acknowledged, False if game is not running.
        """
        try:
            handle = win32file.CreateFile(
                cls.PIPE_NAME,
                win32file.GENERIC_READ | win32file.GENERIC_WRITE,
                0,
                None,
                win32file.OPEN_EXISTING,
                0,
                None
            )
            # Send Command Buffer
            win32file.WriteFile(handle, command.encode("utf-8"))

            # Read Engine Acknowledgment
            _, response = win32file.ReadFile(handle, 256)
            win32file.CloseHandle(handle)

            return b"ACK_QUEUED" in response
        except Exception:
            # Game is not running or proxy DLL is not loaded
            return False

# UI Event Handler Implementation:
def on_btn_force_legendary_click():
    is_success = FLiLiveBridge.send_command("FORCE_LEGENDARY_EVENT")
    if is_success:
        print("[IPC] Command sent successfully. Event queued on Game Thread.")
    else:
        print("[IPC] Game process not detected or DLL connection unavailable.")


# ==============================================================================
# SECTION 8: IMPLEMENTATION VERIFICATION & REVERSE ENGINEERING CHECKLIST
# ==============================================================================

Pre-Flight Validation Protocol:
  [ ] Byte-Roundtrip Test: Execute unpack() on unmodified save file, then 
      execute pack(). Confirm exact file boot without corruption alerts.
  [ ] Anti-Cheat Bypass: Confirm game launches with proxy DLL and bypasses 
      EAC launcher integrity checks to avoid silent save rollbacks.
  [ ] GVAS Property Walk: Validate parser correctly identifies FName "None" 
      terminator across CharacterData and InventoryData struct arrays.
  [ ] IPC Named Pipe Connection: Test client handshake with game running to 
      verify no thread hangs or pipe deadlocks occur during rapid toggles.
  [ ] Game Thread Safety: Ensure ProcessEvent hook captures the queued flag 
      and executes all spawn logic inside the UE5 main thread to prevent 
      access violation crash 0xC0000005.
```
