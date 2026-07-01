# `sale_apu`

This repository contains the public source bundle for the Odoo 18 Community addon `sale_apu`.

## Layout

- `sale_apu/` - installable Odoo addon

## Coolify / Odoo Usage

Use the repository as the contents of the Odoo extra addons volume.

With your compose layout, the Odoo service already mounts:

```yaml
volumes:
  - 'odoo-extra-addons:/mnt/extra-addons'
```

Clone this repository directly into that mounted directory:

```bash
git clone https://github.com/andreseagle1927/sale_apu.git /mnt/extra-addons
```

Then restart Odoo or update the Apps list so it detects `sale_apu`.

## Notes

- `.env` stays local and is ignored by git.
- Only addon source and documentation are tracked here.
- Module details live in [`sale_apu/README.md`](sale_apu/README.md).
