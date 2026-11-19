# Unraid Community Applications

This repository follows the layout of the official
[Unraid Community Apps starter](https://github.com/unraid/unraid-community-apps-starter):
`ca_profile.xml` lives in the root and the Docker app XML lives under `templates/`.
There are no plugin wrappers because this project is a Docker application.
The existing GPL-3.0 license is retained; the starter's MIT license is not copied.

## Publication status

The template is prepared for `ghcr.io/antoblu99/discord-music-bot:latest`.
The image and these new raw GitHub files are not available until the maintainer
pushes the changes and publishes the image. The app has not been submitted to or
approved by Community Applications. Local XML checks do not replace CA Validate,
Scan, or testing on a real Unraid host.

## Install from Apps (after approval)

1. In Discord, create a dedicated application and bot, then invite it using the
   `bot` and `applications.commands` scopes. Grant View Channel, Send Messages,
   Connect, and Speak permissions in the intended channels.
2. Reset any token used by the legacy bot and stop every old instance.
3. Search for **discord-music-bot** in Unraid's Apps tab and select Install.
4. Enter **Discord bot token** and **Discord server ID**. Leave bridge networking
   and privileged mode disabled. No host ports, WebUI, or appdata mount are needed.
5. Review the advanced queue, duration, and idle timeout settings, then Apply.
6. Check container logs for successful command synchronization. Join a voice
   channel and use `/play` in your server to validate playback.

The image uses UID 10001. It does not implement PUID/PGID and has no persistent
files requiring ownership mapping. Downloaded tracks use a 1 GiB `/tmp` tmpfs;
adjust this in Extra Parameters if necessary. Temporary tracks and queues are
discarded when the container stops. The template supplies the same filesystem,
capability, process-reaping, and log limits as Compose. Outbound HTTPS and Discord
voice UDP are required. The published workflow targets Unraid's amd64 hosts.

The token is masked in the form, but masking does not encrypt Docker environment
variables or your saved Unraid user XML. Keep those templates and backups private.
Never submit a configured `my-*.xml` containing credentials to this repository.
Startup removes global slash commands belonging to the configured application and
replaces its commands in the specified server; use a dedicated application.

## Maintainer release and submission

1. Review and push the application, `ca_profile.xml`, `templates/discord-music-bot.xml`,
   `icon.svg`, `icon.png`, and this documentation to `main` in
   `antoblu99/Discord-Music-Bot`. Keep one XML per Docker application.
2. Push a reviewed version tag such as `v1.0.0` on a commit from `main`, or run the
   **Publish container image** GitHub Actions workflow manually on `main`. It runs
   tests and publishes `latest`, a commit-specific tag, and (for releases) the
   version tag without the `v` prefix to GHCR. The workflow
   uses the automatically supplied `GITHUB_TOKEN`; no personal token is embedded.
3. In GitHub package settings, make the container package public. Verify an
   unauthenticated `docker pull ghcr.io/antoblu99/discord-music-bot:latest` from a
   clean client. Publishing a workflow file alone does not create an image.
4. Verify that the profile and app icon URLs, Project URL, ReadMe URL, and raw
   TemplateURL resolve publicly. TemplateURL must point to this exact XML file.
   The Project link provides the required Project/Support metadata. No fictitious
   forum thread, invite, screenshot, or donation URL is supplied.
5. Install and test on an Unraid host: two queued public YouTube tracks,
   pause/resume/skip/stop, restart, and one idle disconnect notification. Confirm
   the token stays out of logs and the public template remains empty of secrets.
6. Open [Community Apps submission](https://ca.unraid.net/submit), supply the
   repository, and run **Validate** and **Scan**, as required by the official
   starter. Resolve reported issues before submitting. Check the current
   [submission help](https://ca.unraid.net/submit/help) for any additional rules.

Keep the image, template variables, and documentation in sync for future releases.
The optional **MediaApp:Music** category can be checked using Unraid's Application
Categorizer plugin. No arbitrary MinVer/MaxVer compatibility bounds are advertised
without corresponding Unraid testing.

## Local template test before publication

To install an image built by GitHub without configuring a registry, open the
repository's **Actions > CI** page, select the successful run for your commit on
`main`, and download the **discord-music-bot-linux-amd64** artifact. GitHub requires
sign-in to download artifacts. Unzip the downloaded artifact, copy the contained
`discord-music-bot-linux-amd64.tar.gz` to your Unraid host, and run:

```sh
docker load --input discord-music-bot-linux-amd64.tar.gz
```

This loads `discord-music-bot:local` and a commit-specific tag. Artifacts expire
after seven days; rerun CI to create a new download. The artifact contains the
image, not your token or configured `.env`. Use it with the local template below
or the Docker CLI command in the root README (skip its build step).

Build the image on Unraid with `docker build -t discord-music-bot:local .`.
Skip this build if you loaded the GitHub artifact instead.
Place a copy of `templates/discord-music-bot.xml` at
`/boot/config/plugins/dockerMan/templates-user/my-discord-music-bot.xml`, change
Repository in that local copy to `discord-music-bot:local`, and select it from
Docker > Add Container > Template. Configure the variables and Apply. Do not
overwrite an existing user template, or commit the configured copy back to Git.
The main template must keep its public GHCR repository for CA submission.

Docker CLI and Compose remain supported independently of Community Applications;
see the root README for both workflows.
