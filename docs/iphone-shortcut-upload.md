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
- Body: selected photo file bytes. In Shortcuts, set `Request Body` to `File`
  and bind it to the current selected photo.
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

## Troubleshooting

If the server logs this:

```text
POST /upload HTTP/1.1" 400 Bad Request
```

and the response body is:

```json
{"detail":"Upload body is empty"}
```

the iPhone reached the server, but Shortcuts did not send the photo bytes. This
usually happens after copying or editing a Shortcut: the `File` field appears to
exist, but its variable binding is empty.

Fix it on the iPhone:

- Open the Shortcut.
- Open the `Get Contents of URL` action.
- Set `Request Body` to `File`.
- Re-select the current photo variable in the `File` field.
- Run the Shortcut again.

If the server logs this instead:

```text
WARNING: Invalid HTTP request received.
```

check that the URL starts with `http://`, not `https://`, and remove any trailing
full-width spaces from the URL.

## Local Deleted Markers

When a photo is deleted through ZeroTraceBrowser, the root workspace records a
local deleted marker keyed by the photo strict hash. Later iPhone uploads with
the same content return `skipped_deleted_locally` and are not re-imported.

This only applies to photos deleted by ZeroTraceBrowser after this marker logic
exists. Old deletions without a marker can still be imported again.

## Storage

Imported files are copied into the current active image root, grouped by date:

```text
<active_root>/YYYY/MM/DD/<filename>
```

Upload metadata and device identity are stored in the current root workspace:

```text
data/roots/<root_id>/workspace.sqlite3
```

Local deleted markers are stored in the same database table:

```text
local_deleted_markers
```

The upload is copy-only. It does not delete photos from the iPhone.
