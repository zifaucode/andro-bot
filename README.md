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

### 4. Hubungkan Bot ke Layar Android (Akses ADB)

Agar Termux (Bot) bisa "menyentuh" layar HP secara otomatis, Anda harus memberinya izin akses ADB lokal. **Pilih salah satu dari 2 metode di bawah ini:**

#### METODE A: Bantuan PC / Komputer (🌟 Sangat Direkomendasikan)
Metode ini sangat diandalkan karena Anda hanya perlu colok kabel selama 10 detik. Setelahnya, Terminal Termux memiliki akses nirkabel permanen ke layar HP menggunakan Port `5555` tanpa perlu diacak (bypass keamanan Android 11+).

*(Persiapan PC: Pastikan Anda memiliki aplikasi ADB di Windows. Jika belum, download [Platform Tools ini (6 MB)](https://dl.google.com/android/repository/platform-tools-latest-windows.zip) lalu Ekstrak/Unzip ke sebuah folder. Anda juga bisa menggunakan `adb.exe` bawaan LDPlayer jika pernah menginstallnya).*

1. Di HP: Aktifkan **USB Debugging** (Debugging USB) pada Opsi Pengembang.
2. Colokkan HP ke PC menggunakan kabel data.
3. Di PC: Buka folder hasil ekstrak *platform-tools*, klik kiri *address bar* folder di atas, ketik **`cmd`** lalu tekan Enter. (Ini akan membuka Terminal CMD).
4. Di Terminal CMD PC, ketik: 
   ```cmd
   adb.exe devices
   ```
   > 💡 **PENTING:** Jika terminal memunculkan kata `unauthorized`, lirik layar HP Anda sekarang! Centang pilihan *"Always allow from this computer"* lalu klik **Izinkan / Allow**.
5. Setelah layar diizinkan, jalankan kembali `adb.exe devices`. Jika status sudah terbaca `device`, eksekusi perintah sakti pembuKa port ini:
   ```cmd
   adb.exe tcpip 5555
   ```
   *(Tanda sukses: Akan muncul respons "restarting in TCP mode port: 5555").*
6. Selesai! Silakan **cabut selamanya kabel datanya**. Mulai sekarang Termux/Script akan otomatis terkoneksi ke port `5555` dengan sakti (kecuali jika suatu saat HP Anda di-restart/habis baterai, maka Anda tinggal mencoloknya sebentar lagi).

#### METODE B: Tanpa Bantuan PC (Wireless Debugging Android 11+)
Jika Anda sama sekali tidak memiliki komputer, Android 11+ memiliki tingkat keamanan ganda yang mewajibkan Anda memasukkan *PIN Pairing*.

> ⚠️ **Trik Penting:** Buka Termux dalam fitur **Jendela Mengambang (Floating Window / Pop-up view)** atau **Split-screen** bersamaan dengan aplikasi Pengaturan HP. Jika Anda pindah aplikasi (Recent app), port pairing Android akan langsung diganti lagi oleh sistem!

1. Ke **Pengaturan -> Developer Options -> Wireless Debugging** (Didebug Nirkabel).
2. Klik opsi **Pair device with pairing code** (Pasangkan dengan kode). Akan muncul PIN 6-digit dan IP:PORT *sementara* (misal: `192.168.1.5:41414`).
3. Dari jendela Termux mengambang, ketik perintah *pairing*:
   ```bash
   adb pair 127.0.0.1:PORT_YANG_TAMPIL
   # Contoh: adb pair 127.0.0.1:41414
   ```
4. Masukkan kode 6-digit PIN. Jika muncul `Successfully paired`, tutup pop-up di layar Pengaturan. Anda sekarang siap menjalankan bot!

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

## Perekaman Macro (Web Macro Recorder)

BOT-ANDRO dilengkapi dengan **Macro Recorder berbasis browser** yang memungkinkan Anda merekam urutan aksi tap/swipe langsung dari tampilan layar HP secara visual — tanpa perlu menebak koordinat secara manual.

### Cara Membuka Macro Recorder

Setelah bot berjalan (`bash start.sh`), buka URL berikut di browser:
```
https://[URL-CLOUDFLARE-ANDA]/recorder
```
*(Anda juga bisa klik tombol **"Recorder"** dari halaman Dashboard)*

---

### Langkah Merekam Macro Baru

#### 1. Ambil Screenshot Layar HP
Klik tombol **`🔄 Refresh`** di bagian kiri halaman Recorder.
Layar HP Anda saat ini akan ditampilkan sebagai gambar interaktif yang bisa diklik.

#### 2. Pilih Mode Aksi

| Mode | Kegunaan |
|---|---|
| **Tap Mode** | Klik satu titik pada screenshot untuk merekam aksi ketuk tombol. |
| **Swipe Mode** | Klik-tahan lalu seret untuk merekam gestur geser (scroll). |
| **Wait** | Tambah jeda/delay (misal 2000ms) antar step. |

#### 3. Rekam Step Satu per Satu

**Untuk Tap:**
1. Pastikan mode aktif adalah **TAP MODE** (tombol berwarna ungu).
2. Klik langsung pada bagian layar yang ingin ditekan (misal: tombol "Topup").
3. Akan muncul jendela kecil meminta **label** (nama step, contoh: `Klik Tombol Topup`). Isi lalu klik OK.
4. Step otomatis masuk ke daftar di panel kanan.

**Untuk Swipe/Scroll:**
1. Aktifkan **SWIPE MODE** (tombol berwarna hijau).
2. Klik-tahan pada titik awal gestur di screenshot, lalu seret ke titik akhirnya dan lepaskan.
3. Garis hijau akan tergambar menunjukkan jalur geseran yang direkam.

**Untuk Aksi Lain (tab Actions):**
Klik tab **⚡ Actions** di panel kanan untuk menambah aksi tambahan:
- **Input Text** — Mengetikkan teks (misal: memasukkan ID Player).
- **BACK** — Menekan tombol kembali Android.
- **HOME** — Menekan tombol Home Android.
- **Launch App** — Membuka aplikasi tertentu berdasarkan *package name*.
- **Check Screen** — Memeriksa apakah layar mengandung warna/region tertentu sebelum lanjut.
- **Screenshot** — Mengambil screenshot sebagai bukti langkah.

#### 4. Susun Ulang / Hapus Step
Di panel kanan tab **📋 Steps**, setiap step yang direkam dapat:
- **Diurutkan ulang** menggunakan tombol `▲` dan `▼`.
- **Dihapus** menggunakan tombol `🗑`.

#### 5. Preview JSON Macro
Klik tab **`</>` JSON** di panel kanan untuk melihat hasil rekaman dalam format file JSON yang akan digunakan bot.

#### 6. Test Run (Uji Coba Langsung)
Klik tombol **`▶ Test Run`** di bagian bawah untuk langsung mengeksekusi seluruh rangkaian step yang direkam ke HP Anda secara real-time.

#### 7. Simpan Macro
Klik tombol **`💾 Simpan Macro`**. File macro akan tersimpan otomatis ke folder:
```
bot-worker/macros/[nama-macro].json
```

---

### Contoh Rangkaian Macro Topup

```
Step 1: Tap (Launch App "com.game.topup")
Step 2: Wait 2000ms
Step 3: Tap tombol "Topup" → (540, 980)
Step 4: Wait 1000ms
Step 5: Tap kolom "ID Player" → (540, 600)
Step 6: Input Text → {{id_player}}
Step 7: Tap tombol "Bayar" → (540, 1200)
Step 8: Wait 2000ms
Step 9: Screenshot (bukti transaksi)
Step 10: Tap BACK → kembali ke Home
```

> 💡 **Tips:** Teks dengan format `{{nama_variabel}}` akan diisi otomatis oleh Bot sesuai data dari request Laravel (misal `{{id_player}}`, `{{amount}}`).

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
