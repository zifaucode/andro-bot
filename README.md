# BOT-ANDRO

Bot automation yang berjalan **langsung di device Android fisik** via Termux — tanpa emulator, tanpa kabel USB ke PC.

## Arsitektur

```
[Laravel Server]
      │
      │  HTTPS (Cloudflare Quick Tunnel URL)
      ▼
[HP Android / Termux]
  ├── cloudflared  ← tunnel ke Cloudflare
  ├── FastAPI :8000 ← API server
  └── Bot Worker (Python)
       └── ADB 127.0.0.1:5555 ← kontrol diri sendiri
```

## Perbedaan dari BOT-EMU (LDPlayer)

| | BOT-EMU | BOT-ANDRO |
|---|---|---|
| Target ADB | `emulator-5554` (LDPlayer) | `127.0.0.1:5555` (diri sendiri) |
| ADB binary | `C:\LDPlayer\...\adb.exe` | `adb` (dari Termux) |
| Launch emulator | `ldconsole.exe` | Tidak perlu |
| OS | Windows | Android (Termux) |
| Tunnel | `cloudflared.exe` di Windows | `cloudflared` ARM64 di Termux |

## Setup (Pertama Kali)

### 1. Install & Menghapus Termux

**Menginstall Termux:**
> ⚠️ JANGAN install Termux dari Google Play Store karena versinya usang dan tidak bisa menginstall `android-tools`.
> **Download & Install dari F-Droid:** https://f-droid.org/packages/com.termux/

Setelah install selesai, buka aplikasi Termux dan tunggu sejenak sampai muncul baris perintah (terminal).

**Menghapus Termux / Project:**
- **Menghapus Project Bot:** Jika ingin menghapus bot atau mengulang instalasi (clone ulang), jalankan perintah: `rm -rf ~/andro-bot`
- **Menghapus Keseluruhan Termux:** Jika terjadi error sistem Termux, buka Pengaturan HP -> Aplikasi -> Termux -> **Clear Data**, lalu buka ulang aplikasinya.

### 2. Copy project ke HP (Termux)

Option A — via Git (Disarankan):
```bash
pkg update && pkg upgrade -y
pkg install git -y
git clone https://github.com/zifaucode/andro-bot.git ~/andro-bot
```

Option B — via USB transfer:
```bash
# Copy folder andro-bot ke /sdcard/andro-bot (Internal Storage) dulu
# Lalu buka Termux dan ketik:
cp -r /sdcard/andro-bot ~/andro-bot
```

### 3. Jalankan Setup
```bash
cd ~/andro-bot
bash setup_termux.sh
```

Script ini akan otomatis:
- ✅ Update Termux packages
- ✅ Install Python, android-tools (ADB), wget
- ✅ Install FastAPI, uvicorn, python-dotenv
- ✅ Install cloudflared (ARM64/ARM)
- ✅ Buat file `.env` dari `.env.example`

### 4. Aktifkan ADB Wireless di HP

**Android 10:**
```
Settings → Developer Options → ADB over network → ON
(beberapa ROM: "ADB via WiFi")
```

**Android 11+:**
```
Settings → Developer Options → Wireless Debugging → ON
```

Lalu di Termux:
```bash
adb connect 127.0.0.1:5555

# Verifikasi:
adb devices
# Output yang diharapkan:
# 127.0.0.1:5555    device
```

### 5. Jalankan Bot & Akses Web GUI

```bash
bash ~/andro-bot/start.sh
```

Output yang diharapkan:
```
╔══════════════════════════════════════╗
║          BOT-ANDRO Startup           ║
╚══════════════════════════════════════╝

[1/3] Menghubungkan ADB ke device lokal...
    ✅ ADB terkoneksi ke 127.0.0.1:5555

[2/3] Menjalankan FastAPI Server...
    ✅ FastAPI berjalan (PID: 12345)

[3/3] Menjalankan Cloudflare Quick Tunnel...

╔══════════════════════════════════════════════════╗
║  ✅ BOT-ANDRO SIAP!                              ║
║  🌐 URL: https://xxx-xxx.trycloudflare.com       ║
╚══════════════════════════════════════════════════╝
```

**Langkah Terakhir (Sangat Penting):**
1. Buka URL Cloudflare di atas melalui browser (HP/PC) dan tambahkan `/setup`. 
   Contoh: `https://xxx.trycloudflare.com/setup`
2. Ikuti **Setup Wizard** modern di browser untuk:
   - Membuat/mengganti API Key dan Password Dashboard.
   - Tes koneksi ADB.
3. Setelah selesai, Anda akan masuk ke **Web Dashboard** interaktif tempat Anda menekan tombol "Start Bot", mengedit *Macro*, memonitor log, dan ubah `.env` tanpa menggunakan command line lagi!

**⚠️ Simpan URL Cloudflare dan API Key Anda ke konfigurasi Laravel Anda!**

### 6. Stop Server & Tutup Termux (Clean Shutdown)

Jika Anda ingin mematikan bot, menonaktifkan *Wake-Lock* (agar baterai tidak terkuras saat HP standby), serta menutup Termux sepenuhnya:

1. **Jalankan script `stop.sh`** untuk mematikan FastAPI, Cloudflared tunnel, proses Python, dan menormalkan *Wake-Lock* secara otomatis:
```bash
bash ~/andro-bot/stop.sh
```

2. **Keluar dari Termux (Kill Terminal):**
Agar Termux tidak terus memakan memori/RAM di background, selalu tutup sesi dengan rapi menggunakan perintah:
```bash
exit
```
> 💡 **Penting:** Jika muncul notifikasi "Termux: x sessions running", Anda juga bisa tekan tombol **"EXIT"** secara langsung pada bar notifikasi Android untuk melakukan proses Kill secara aman.

## Koordinat Macro

File macro ada di `bot-worker/macros/topup.json`.

Koordinat tap disesuaikan dengan **resolusi layar HP Anda**.
Gunakan `adb shell getevent -l` atau screenshot + editor gambar untuk cari koordinat yang tepat.

Cek resolusi layar:
```bash
adb -s 127.0.0.1:5555 shell wm size
```

## Cara Kirim Request dari Laravel

```php
// Contoh Laravel
$response = Http::withHeaders([
    'X-API-Key' => env('BOT_API_KEY'),
])->post('https://xxx.trycloudflare.com/api/trigger', [
    'transaction_id' => 'TXN' . time(),
    'task_type'      => 'topup',
    'id_player'      => '12345678',
    'amount'         => '100',
]);
```

## Agar Termux Tidak Di-kill Android

```bash
# Di Termux — aktifkan wakelock
termux-wake-lock

# Di Settings Android:
# Battery → Termux → Unrestricted (tidak batasi background)
```

## Masalah Umum

| Masalah | Solusi |
|---|---|
| `adb: command not found` | `pkg install android-tools` |
| ADB connect gagal | Aktifkan Wireless Debugging di Developer Options |
| Port 5555 tidak bisa | Android 11+: cek port di Settings → Wireless Debugging |
| Cloudflared tidak install | Cek arsitektur: `uname -m` |
| FastAPI crash | Cek log: `cat ~/andro-bot/logs/fastapi.log` |
| Termux tertutup saat idle | Jalankan `termux-wake-lock` |
