# Grimmory

A custom Home Assistant integration for [Grimmory](https://grimmory.org). The integration uses the Grimmory API.

Currently provides:
- Book count
- Grimmory version and update information
- Kobo Sync status
- Last read book
- Choose a specific Grimmory library or all libraries during setup
- Refresh libraries with a button: refreshes the selected library, or every library when **All libraries** is selected.

## Installation


### Using HACS
Add this repository to HACS (Marketplace) as custom repository and install the integration.

[![Open Grimmory in HACS](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=Martreides&repository=ha-grimmory&category=integration)

### Manual
Copy `custom_components/grimmory` to the `custom_components` directory in your Home Assistant configuration.

Restart Home Assistant and add Grimmory through **Settings → Devices & services**.

## Note

This integration is actively developed and may be unstable. Features and behaviour may change.
