function updateTrackerSheet() {
  const sheet = SpreadsheetApp.getActiveSpreadsheet().getActiveSheet();
  const data = sheet.getDataRange().getValues();
  const apiKey = 'YOUR_GOOGLE_MAPS_API_KEY';  // Replace with your own Google Maps API key

  for (let i = 1; i < data.length; i++) {
    const row = i + 1;

    const lat = data[i][2];       // Column C
    const lon = data[i][3];       // Column D
    const speed = data[i][4];     // Column E
    const battery = data[i][5];   // Column F
    const location = data[i][6];  // Column G
    const mapImage = data[i][7];  // Column H

    if (!lat || !lon) continue;

    const mapUrl = `https://www.google.com/maps/search/?api=1&query=${lat},${lon}`;

    // --- Address (hyperlinked) in column G ---
    const needsAddress = !location || !String(location).startsWith('=HYPERLINK');
    if (needsAddress) {
      try {
        const geoUrl = `https://maps.googleapis.com/maps/api/geocode/json?latlng=${lat},${lon}&key=YOUR_GOOGLE_MAPS_API_KEY`;
        const response = UrlFetchApp.fetch(geoUrl);
        const json = JSON.parse(response.getContentText());

        let address = "Unknown location";
        if (json.status === "OK" && json.results.length > 0) {
          address = json.results[0].formatted_address;
        }

        const clickable = `=HYPERLINK("${mapUrl}", "${address.replace(/"/g, '')}")`;
        sheet.getRange(row, 7).setFormula(clickable); // Column G
      } catch (err) {
        Logger.log(`Geocoding error on row ${row}: ${err}`);
      }
    }

    // --- Static map image in column H ---
    if (!mapImage || mapImage === "") {
      try {
        const staticMapUrl = `https://maps.googleapis.com/maps/api/staticmap?center=${lat},${lon}&zoom=15&size=300x150&maptype=roadmap&markers=color:red|${lat},${lon}&key=YOUR_GOOGLE_MAPS_API_KEY`;
        const imageFormula = `=IMAGE("${staticMapUrl}")`;
        sheet.getRange(row, 8).setFormula(imageFormula); // Column H
      } catch (err) {
        Logger.log(`Map image error on row ${row}: ${err}`);
      }
    }
  }

  Logger.log("✅ Tesla Tracker sheet updated.");
}