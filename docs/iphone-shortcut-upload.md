# iPhone Shortcut Upload

ZeroTraceBrowser accepts iPhone Shortcut uploads through a local HTTP POST.
The request body is the image bytes. Metadata is passed through headers.

## Server

Start the app on the LAN:

```powershell
.\start-dev.ps1
```

The script listens on `0.0.0.0:8000` and adds detected local IPv4 addresses to
`ZTB_TRUSTED_HOSTS`.

If the iPhone cannot open the page, check:

- iPhone and Windows are on the same Wi-Fi network.
- Windows Firewall allows inbound access to Python or TCP port `8000`.
- Safari on iPhone can open `http://<windows-ip>:8000/`.

## Shortcut URL

Use either endpoint:

```text
http://<windows-ip>:8000/api/iphone/upload
http://<windows-ip>:8000/upload
```

## Required Request Shape

- Method: `POST`
- Body: selected photo file bytes
- Headers:

```text
X-Original-Filename: IMG_0948.jpeg
X-Original-CreateDate: 2026/05/17 10:26:47 JST
X-Original-UpdateDate: 2026/05/17 11:42:31 JST
X-Original-FileSize: 2.5 MB
X-Original-FileType: jpeg
X-Original-DeviceName: Peng Yufei s iPhone 13
X-Original-DeviceModel: iPhone
```

Recommended headers for multi-person use:

```text
X-ZTB-Uploader: Peng Yufei
X-ZTB-DeviceId: pyf-iphone-13-main
```

`X-ZTB-DeviceId` is the stable identity used in the root workspace database. If
it is omitted, ZeroTraceBrowser uses `X-ZTB-Uploader::X-Original-DeviceName`.
If both are omitted, it falls back to `X-Original-DeviceName`.

## iPhone Permissions

If Shortcuts says it has no permission to transfer photos, fix the iPhone side:

- Open `Settings > Privacy & Security > Photos > Shortcuts`.
- Allow full photo access, or allow access to the selected photo.
- Reopen the Shortcut and approve any photo/network permission prompts.

## Storage

Imported files are copied into the current active image root, grouped by date:

```text
<active_root>/YYYY/MM/DD/<filename>
```

Upload metadata and device identity are stored in the current root workspace:

```text
data/roots/<root_id>/workspace.sqlite3
```

The upload is copy-only. It does not delete photos from the iPhone.
