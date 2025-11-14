# onedrive_file_explorer
Tools to list, explorer and download files from one drive folders. Support discovery of orphan drives and gives a shell-like command tools  


Obviously ChatGPTed



one_enum enumerates the one-drive space. Be careful with the workers (429 limited)

```
python one_emum.py \
  --tenant-id YYYYYYYYYY \
  --client-id XXXXXXXXXXXXXXX \
  --client-secret "A~..." \
  --depth 3 \
  --workers 5
```


ms_file_explorer uses the username or the found drive_id (even if the user were deleted) to give a shell with read-only purposes (put not yet implemented)

```
python explorer4.py  --tenant-id XXXXXXXXXXXXXXXXXXX --client-id YYYYYYYYYYYYYYYYYYY --client-secret AAAAAAAAAAAAAAAAAAAAAA --drive-id 'b!JJJJJJJJJJJJJJJJJJJJJJJJJJ'
```

Supports:
>cd
>download
