# Nourish Nutrition for Home Assistant

An experimental, community-built, **Marketplace-installable** Home Assistant integration for the Nourish nutrition tracking website. It displays your logged nutrient progress and goals as Home Assistant sensors, automatically syncs at **11:56 PM** Home Assistant local time, and offers a **Sync now** button and action.

> **Early preview / unofficial integration.** Not affiliated with Nourish. This project uses a browser-observed **undocumented** endpoint and has **not yet been tested end-to-end in a real Home Assistant installation**. The interface and authentication behavior may change. Nourish's terms may restrict automated access; use only with authorization. Do not share tokens, cookies, browser console outputs containing secrets, or private nutrition data. If you are not comfortable with the technical browser step, wait for an officially supported sign-in method.

## What you get

- Sensors for each nutrient returned by the Nourish goals API, with a **today** progress sensor and a **goal** sensor.
- A **Last sync** timestamp sensor.
- Automatic synchronization at **11:56 PM in the timezone configured for Home Assistant**.
- A **Sync now** button and the `nourish.sync_now` action.
- Automatic access-token refreshing using a refresh token, including handling **rotated refresh tokens**.
- Built-in Home Assistant **Repairs → Reauthentication** when the saved credentials stop working.

**Important limitations:** There is no direct official OAuth authorization flow in Home Assistant. Setup uses a one-time browser helper to copy secret connection details. The refresh token may be revoked or invalidated by a different browser session. Currently there is **no historical backfill**, and the only API call is `/todays-goals`. Some responses may use progress objects not yet supported by the parser, in which case progress sensors show `unknown`, not invented values. This integration has not been verified for inclusion in the default Marketplace catalog.

## Installation

### 1. Install from Home Assistant Marketplace (Home Assistant 2026.11+)

**Marketplace is built into Home Assistant 2026.11 and newer.** You do not need to install HACS separately. This project is not yet in the default Marketplace catalog, so add it using its GitHub link:

1. In Home Assistant, sign in as an **administrator** and go to **Settings → Marketplace**.
2. If this is your first visit, review and accept the Marketplace warning.
3. Select **Add from link** in the upper-right corner.
4. If prompted, **connect your GitHub account** using the guided device sign-in. A GitHub connection is required for custom repositories; it grants Marketplace read-only access to public GitHub data.
5. In **GitHub link**, paste `https://github.com/ChadJPetersen/home-assistant-nourish` and select **Add**.
6. Marketplace should identify the repository as an **Integration**. If prompted to choose a type, choose **Integration** and select **Add** again.
7. Open **Nourish Nutrition** from the Marketplace listing, select **Install**, and **restart Home Assistant** if prompted.
8. Continue with **Step 2: Obtain connection details** below, then go to **Settings → Devices & services → Add integration** to configure Nourish.

If you use **Home Assistant older than 2026.11**, follow the legacy [HACS](https://www.hacs.xyz/) custom-repository installation workflow instead.

**Manual installation:** You can copy the `custom_components/nourish` folder into the `custom_components` directory inside your Home Assistant configuration folder, then restart. Marketplace is recommended because it handles updates.

For more information, see the [official Home Assistant Marketplace instructions](https://www.home-assistant.io/integrations/marketplace/#custom-repositories).

### 2. Obtain connection details

**This is the only technical step in the preview version.** It is best done in a **separate browser profile** that you use only for this integration, because Nourish might rotate refresh tokens. Do not share its credentials with anyone, including maintainers. Only run console code you have reviewed and trust; the code below reads a refresh token from the browser's local storage and copies it to your clipboard without sending it to us.

1. In a desktop Chrome browser, go to [app.nourish.com](https://app.nourish.com/) and sign in.
2. Press **F12** (or **Ctrl+Shift+J**) to open Developer Tools, then select **Console**.
3. Carefully review this project’s **Connection helper** code below. Never paste unrelated snippets from messages or strangers into Developer Tools.
4. Paste the code into the console and press **Enter**. Chrome may require you to confirm that you intend to paste into Developer Tools.
5. If successful, you will see `Connection details copied to clipboard. Keep them private.`
6. Return to Home Assistant promptly and paste the copied JSON into the **Connection details** field. Don't paste it into GitHub issues, chat, email, screenshots, or logs.
7. Clear your clipboard after completing setup. You may close the separate browser profile afterward.

#### Connection helper (runs locally inside the Nourish browser tab)

```javascript
(() => {
  const key = Object.keys(localStorage).find(
    item => item.includes("auth0spajs") && item.includes("offline_access")
  );
  if (!key) {
    console.error("No Nourish session found. Sign in and reload.");
    return;
  }

  let auth;
  try {
    auth = JSON.parse(localStorage.getItem(key));
  } catch {
    console.error("Nourish session data could not be decoded.");
    return;
  }

  const refreshToken = auth?.body?.refresh_token;
  const clientId = auth?.client_id;
  const accessToken = auth?.body?.access_token;
  if (!refreshToken || !clientId || !accessToken) {
    console.error("Required session data is missing. Sign in again.");
    return;
  }

  try {
    const jwtPayload = accessToken.split(".")[1];
    const base64 = jwtPayload.replace(/-/g, "+").replace(/_/g, "/");
    const padded = base64.padEnd(Math.ceil(base64.length / 4) * 4, "=");
    const claims = JSON.parse(atob(padded));
    const patientId = claims["https://app.usenourish.com/patientId"];
    if (!patientId) {
      console.error("Could not find your patient ID in the session.");
      return;
    }

    const details = {
      clientId,
      patientId: String(patientId),
      refreshToken,
      deviceTimeZone: Intl.DateTimeFormat().resolvedOptions().timeZone
    };

    // Only copies data to your own clipboard. No network request is made.
    copy(JSON.stringify(details));
    console.log("Connection details copied to clipboard. Keep them private.");
  } catch {
    console.error("Could not prepare connection details. Sign in again.");
  }
})();
```

The helper copies a JSON object containing `patientId`, `clientId`, `refreshToken`, and `deviceTimeZone`. **Treat the whole JSON as a secret**. It can provide access to sensitive health information. The helper does not expose your access token in the output.

### 3. Add the integration

1. In Home Assistant, go to **Settings → Devices & services**.
2. Select **Add integration**.
3. Search for **Nourish Nutrition**.
4. Paste the copied JSON in the **Connection details** field and submit.
5. Home Assistant will try to contact Nourish to validate the credentials. If successful, your new device and sensors will appear.

No `configuration.yaml` changes are needed.

### 4. Sync on demand

Open **Settings → Devices & services → Nourish Nutrition → Nourish Nutrition** and press the **Sync now** button.

Or in **Developer Tools → Actions**, select **Nourish: Sync now**. YAML equivalent:

```yaml
action: nourish.sync_now
```

Home Assistant refreshes at startup and at 11:56 PM every day. At local midnight, today's sensors reset to `unknown` until the next sync (the scheduled 11:56 PM reading is stored in Home Assistant history, subject to recorder retention). **This integration does not automatically collect live totals throughout the day**; press Sync now when you want an up-to-date reading.

## If authentication fails: Home Assistant Repairs

When Nourish rejects a refresh token (such as when it has expired, was revoked or was already rotated elsewhere), the integration raises Home Assistant's `ConfigEntryAuthFailed`. Home Assistant **automatically creates a reauthentication repair issue** under **Settings → System → Repairs**. This is built into Home Assistant; the integration does not create a duplicate repair. The repair opens the reconnect form with the steps below. Once reauthentication succeeds, Home Assistant resolves its reauthentication repair issue.

1. Open **Home Assistant → Settings → System → Repairs**.
2. Find the **Nourish Nutrition reauthentication** issue and open it.
3. If you no longer have access in your previous browser profile, sign in to Nourish in a dedicated desktop browser profile.
4. Return to the **Connection helper** above; run it again on the signed-in Nourish tab.
5. Paste the newly copied private connection JSON into the reauthentication form.
6. Submit. The integration checks the new credentials and reconnects without deleting your sensors or their entity IDs.

If no repair appears yet, go to **Settings → Devices & services → Nourish Nutrition**, inspect the integration's status and restart or reload the integration. Network outages are treated differently from rejected credentials and should not trigger a reauthentication repair.

**Security note:** Do not post any of the resulting JSON in GitHub issues. A refresh token is a reusable credential. If accidentally disclosed, sign out/revoke sessions in Nourish where supported, then reconnect using fresh credentials.

## Supported API fields

The integration currently reads the endpoint discovered through the Nourish browser interface:

```text
GET https://app.nourish.com/api/patients/{patientId}/todays-goals?deviceTimeZone={timeZone}
Authorization: Bearer <access token>
```

It selects records where `type === "LOG_NUTRIENT"`, uses `subType` as the nutrient identifier and `goalAmount` as the target. It attempts to extract the first numeric `goalProgress` element (or a recognized amount field). An unfamiliar progress structure remains unavailable until validated against a safely redacted example. Numeric values are treated as the units assigned to familiar nutrient names (kcal/g/mg), which should be verified against real API data before relying on them.

The integration refreshes OAuth credentials through `POST https://auth.nourish.com/oauth/token` using `grant_type=refresh_token`, `client_id`, and the private `refresh_token`. If Nourish rotates the refresh token, Home Assistant saves the replacement in its private config-entry storage. The integration never needs your browser cookies.

## Troubleshooting

| Symptom | What to do |
|---|---|
| Integration not found | Restart Home Assistant after installing through **Settings → Marketplace**; verify the GitHub repository was added as an **Integration** |
| Invalid connection details | Run the helper again and paste the **entire JSON** without modifying field names |
| Login rejected | Re-sign in to Nourish and repeat the helper in a separate browser profile |
| Repair notification | Open **Settings → System → Repairs**, select Nourish reauthentication, and follow the instructions |
| Sensors show unknown | Press Sync now; Nourish may not have data for today's nutrient or may use a currently unsupported progress format |
| Cannot connect | Check internet access from Home Assistant and try again later; Nourish may have changed its API |
| No old entries in history | The current version does not fetch or backfill previous days; recorder stores new sensor states going forward |

## Privacy, security and compatibility

- **Do not commit real credentials or health data.** The integration stores secrets using Home Assistant config-entry storage, not YAML. Secure your Home Assistant installation and its backups.
- This is an **unofficial, undocumented API**. Continued operation and authorization are not guaranteed.
- Refresh-token rotation may invalidate the token held by the browser profile used for setup. Use a dedicated profile, and repeat the repair flow if necessary.
- Data and goals are read-only; this integration does not modify Nourish.
- The API date is evaluated in the browser-provided timezone, while the scheduled run uses Home Assistant's timezone. For best results, keep these set to the same region.
- The integration performs **no periodic polling** aside from the daily scheduled refresh. Manual syncs trigger immediate requests.

## Development

The module parser can be tested without Home Assistant:

```bash
python -m unittest discover -s tests -v
python -m compileall -q custom_components/nourish
```

The repository includes a lightweight GitHub Actions test workflow. End-to-end Home Assistant installation, reauthentication behavior, and sensor mapping should be tested before treating the project as production-ready. Contributions and sanitized response *shapes* are welcome, but **never include real credentials, patient IDs, or identifiable nutrition data** in an issue or pull request.

## License

MIT. See [LICENSE](LICENSE).
