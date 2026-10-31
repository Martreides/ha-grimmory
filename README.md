# Grimmory

An unofficial custom Home Assistant integration for [Grimmory](https://grimmory.org). The integration uses the Grimmory API.

## Requirements

Requires Home Assistant Core 2026.9 or newer. Grimmory uses child devices for tracked books, a feature introduced in [Home Assistant Core 2026.9](https://contributors.home-assistant.io/blog/2026/10/22/child-devices/).

## Features

| Entity | Description |
| --- | --- |
| Book count | Number of books in the selected library, or across all libraries. |
| Bookdrop files pending review | Number of files in Grimmory's bookdrop queue awaiting review. |
| Last read book | Title of the last read book. Authors, series, last-read time, and read progress are available as attributes. |
| Kobo Sync Enabled | Whether Kobo sync is enabled in Grimmory. |
| Refresh libraries | Button to let Grimmory refresh the selected library, or every library when **All libraries** is selected. |
| Rescan bookdrop folder | Button to ask Grimmory to rescan its bookdrop folder. |
| Grimmory version | Update entity showing the installed and latest Grimmory versions. |
| Book read status | A sensor for each tracked book, shown on a child device under Grimmory. |
| Book read progress | A sensor for each tracked book showing progress from the selected source: Grimmory, KOReader, or Kobo. |

## Setup

After installing the integration, add Grimmory from **Settings → Devices & services → Add integration**. Enter the base URL of your Grimmory server (don't forget http:// or https://) and your Grimmory username and password. Then choose a specific library or All libraries, and select the source to use for book reading progress.

To change the library or reading progress source later, open the Grimmory config entry, choose **Configure**, then select **Change additional settings**. You can also use **Reconfigure** from the config entry menu.

## Track an individual book

Open the Grimmory configuration entry, choose **Configure**, then select **Add a book** and enter the book's ID. You can find the ID in the book's URL: for example, in `http://192.168.1.17:6060/book/169?tab=view`, the book ID is `169` (the number after `/book/`).

If you selected a specific library during setup, the book must belong to that library. With **All libraries** selected, books from any library can be added.

To stop tracking a book, open **Configure** and select **Remove a book**.

## Installation


### Using HACS
Add this repository to HACS (Marketplace) as custom repository and install the integration.

[![Open Grimmory in HACS](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=Martreides&repository=ha-grimmory&category=integration)

### Manual
Copy `custom_components/grimmory` to the `custom_components` directory in your Home Assistant configuration.

Restart Home Assistant and add Grimmory through **Settings → Devices & services**.

## Troubleshooting

- **Book is not in the selected library:** Add a book from the configured library, or reconfigure the integration to use All libraries.

If the issue persists, [open an issue](https://github.com/Martreides/ha-grimmory/issues).

## Note

This integration is actively developed and may be unstable. Features and behaviour may change and are currently mainly based on what I use myself.

## License

This project is licensed under the GNU General Public License v3.0 only. See [LICENSE](LICENSE).
