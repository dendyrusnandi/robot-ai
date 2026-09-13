# Knowledge RN AI Bot

Masukkan dokumen perusahaan ke folder `knowledge/`.

Format yang didukung:

- `.pdf`
- `.docx`
- `.md`
- `.txt`

Contoh isi dokumen: profil perusahaan, katalog dan spesifikasi produk, FAQ,
manual penggunaan, kebijakan garansi, layanan, kontak, dan halaman tentang kami.

Saat RN AI Bot dijalankan, dokumen baru atau yang berubah otomatis diekstrak,
dibagi menjadi potongan, lalu dibuatkan embedding. Hasilnya disimpan sebagai
`knowledge/.vector_store.json`. Jangan mengedit file cache tersebut secara manual.

Setelah menambah atau mengganti dokumen, restart aplikasi:

```bash
./start.sh
```

Periksa log berikut:

- `knowledge indexed` berarti indeks baru berhasil dibuat.
- `knowledge ready from cache` berarti cache masih sesuai dan siap digunakan.
- `knowledge disabled` berarti belum ada dokumen yang didukung atau API key tidak tersedia.
