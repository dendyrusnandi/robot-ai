# Knowledge RN AI Bot

## OpenAI Vector Store (aktif)

Isi `knowledge.vector_store_id` di `config.yaml` dengan ID vector store yang
sudah berisi dokumen, misalnya:

```yaml
knowledge:
  enabled: true
  vector_store_id: vs_6ab3cab661708191be05af2341a70785
```

Pastikan `.env` berisi `OPENAI_API_KEY` dari project OpenAI yang sama dengan
vector store tersebut. Saat mode ini aktif, pertanyaan knowledge dicari
langsung melalui OpenAI Vector Store Search API; dokumen tidak perlu diunduh
atau dibuatkan embedding lagi oleh aplikasi.

Log `knowledge ready from OpenAI vector store=...` menandakan konfigurasi siap.

### Tes lewat CLI teks

Mode interaktif tanpa kamera dan audio:

```bash
python3 cli.py
```

Jawaban ditampilkan dengan mode streaming, sehingga teks mulai muncul segera
setelah model menghasilkan bagian pertama jawaban.

Atau kirim satu pertanyaan langsung:

```bash
python3 cli.py "Apa layanan yang tersedia?"
```

Model teks dapat diubah melalui `providers.openai.text_model` di `config.yaml`.

## Dokumen lokal (fallback)

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
Mode lokal ini digunakan jika `vector_store_id` dikosongkan.

Setelah menambah atau mengganti dokumen, restart aplikasi:

```bash
./start.sh
```

Periksa log berikut:

- `knowledge indexed` berarti indeks baru berhasil dibuat.
- `knowledge ready from cache` berarti cache masih sesuai dan siap digunakan.
- `knowledge disabled` berarti belum ada dokumen yang didukung atau API key tidak tersedia.
