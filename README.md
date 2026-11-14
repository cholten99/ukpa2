# ukpa2: the UK Polyamory Association website

The source of <https://ukpolyamory.org>. Plain HTML pages with server-side
includes (`.shtml`), styled with Tailwind from its CDN. There is no build step:
the repo is checked out at `/var/www/ukpa2` on Dave's server and Apache serves
it directly (vhost `/etc/apache2/sites-available/ukpolyamory.conf`), so **a
saved change is live at once**. Commit and push to `cholten99/ukpa2` to keep a
record.

## Layout

```
*.shtml                 top-level pages (index, about, community, privacy, ...)
template.shtml          starting point for a new page
includes/               header.html, footer.html, slideshow.html, pulled in by
                        <!--#include virtual="/includes/..." -->
community-pages/        one page per group, plus index.shtml (the list of them)
                        and example.shtml (a template); images/ for banners
event-pages/            example.shtml, a template for event pages
uk-groups-directory.shtml   table of groups on other platforms
groups-map.shtml        map of every group (see below)
assets/                 slideshow.js; groups-map.json (generated, see below)
resources/              PDFs and images linked from resources.shtml
images/, video/         site media
tools/                  maintenance scripts, not served on the web
styles.css              site-wide styles on top of Tailwind
```

Every page starts with the same head: the Google Ads tag, Tailwind, `/styles.css`
and the favicon. Copy it from `template.shtml` rather than writing it fresh.

## Groups

UKPA lists groups in three places that should agree:

1. **Group pages** (`community-pages/*.shtml`): a full page for a group that
   has given us its details. Each one is a card in `community-pages/index.shtml`.
   These count as confirmed and get a red pin on the map. Put "Last updated:
   Month Year" on the page and refresh it when the group's details change.
2. **The directory** (`uk-groups-directory.shtml`): a table of groups on other
   platforms (Meetup, Facebook, Discord...). Group, Region, Format (In-person,
   Online, or TBD when unknown). These aren't confirmed as current: they get a
   grey pin and a caveat on the map.
3. **The map** (`groups-map.shtml`), built from 1 and 2.

### Adding a group page

1. Copy an existing page in `community-pages/` (or `example.shtml`) and fill
   it in: key facts on the left, details on the right.
2. For a venue or area map, use Leaflet with OpenStreetMap, like
   `london-poly-pub.shtml` (venue) or `bristol-south-west-polyamory.shtml`
   (area). Avoid embedding Google Maps: two older pages (London Poly Munch,
   Ipswich Poly Munch) do, and the privacy page has to cover it.
3. Add a card for it to `community-pages/index.shtml`, in alphabetical order.
4. Add it to `PAGES` in `tools/build-groups-map.py` with the area to pin it to
   (or `None` for a national group). If the group is also in the directory
   under another name, add it to `SAME_AS` so the two merge into one entry.
5. Run the map build (below).

To keep a page private while it's being reviewed: add
`<meta name="robots" content="noindex" />`, don't link it from anywhere, and
list it in `SKIP_PAGES` in the build script. Undo all three when it goes live.

### Groups map

`groups-map.shtml` shows every group on a Leaflet + OpenStreetMap map (no API
key or account), with national and online groups listed underneath. The page
reads `assets/groups-map.json`, which is generated. After changing the
directory or adding or editing a group page, run from the repo root:

```
python3 tools/build-groups-map.py
```

and commit the updated JSON. The script:

- reads the directory table and the group pages, merging a page into its
  directory row when the names match (or via `SAME_AS`);
- places each area with OpenStreetMap's Nominatim service and caches the result
  in `tools/geocode-cache.json`, so only new areas are looked up (Nominatim's
  policy: at most one request a second, and keep the results). Areas it can't
  place by name are steered with `QUERY` (another search term) or `FIXED`
  (coordinates). A pin marks the middle of the area a group covers, not a venue;
- stops with a message if it finds a group page that isn't in `PAGES`;
- sets the "Last updated" date shown on the map only when the group list
  actually changes.

Pins: solid red for groups with a page here, hollow grey for directory-only
groups (unconfirmed). An area with both kinds gets one of each, side by side;
bigger pins mean more groups.

## Privacy and third parties

`privacy.shtml` lists everything that sends visitors' data elsewhere. Keep it in
step when adding anything that loads from another site, and update its "last
updated" date.

- **Google Ads tag** (`AW-17876605291`) on every page. It sets cookies and sends
  visits to Google, for measuring advert campaigns. No adverts are running at
  the moment. UK cookie law (PECR) needs visitors' consent before advertising
  cookies are set, so add a consent banner, or load the tag only after consent,
  before running adverts again.
- **OpenStreetMap** map images on the groups map and most group pages.
- **Google Maps** embeds on the London and Ipswich Poly Munch pages.
- **CDNs:** Tailwind (`cdn.tailwindcss.com`), Leaflet (cdnjs on the groups map,
  unpkg on group pages).

## Security

`.htaccess` keeps these off the web: dotfiles and `.git`, backup and dump files
(`.bak`, `.sql` and the like, including dated copies), `/tools`, and the
Markdown docs (`*.md`). Never leave database dumps, config backups or secrets
in the web root.

## Other docs

- [Automating the Community Calendar](Automating%20the%20Community%20Calendar.md):
  how invites sent to `community-events@ukpolyamory.org` reach the calendar on
  `calendar.shtml` (a Google Apps Script on the `info@` Workspace account).
