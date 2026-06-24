# UKPA Community Events Calendar — Technical Documentation

## Overview

This document describes the setup for automatically adding events to the UK Polyamory Association community events calendar when people send calendar invites to `community-events@ukpolyamory.org`.

## The Problem

The goal was to provide a friendly email address (`community-events@ukpolyamory.org`) that anyone could invite to a Google Calendar event, causing that event to automatically appear on the UKPA community events calendar embedded on the website.

Google Calendar secondary calendars have a long, unfriendly ID address (ending in `@group.calendar.google.com`) which is not suitable for sharing publicly.

## Why Not a Simple Email Forward?

Several simpler approaches were investigated and ruled out:

- **Cloudflare Email Routing** — ukpolyamory.org DNS is at Cloudflare, but the MX records point to Google (Workspace), so Cloudflare Email Routing is not in the mail path and cannot forward anything.
- **Gmail/Workspace forwarding** — Gmail requires a verification link to be clicked before it will forward to any address. A calendar ID cannot click a link.
- **Gmail filter forwarding** — Same verification requirement applies.
- **Workspace email alias** — Adding `community-events` as an alias on an existing user causes all mail to arrive in that user's inbox with no reliable way to filter by original destination address, since Workspace rewrites the `To` header.

## The Solution

A **Google Apps Script** running on a 5-minute timer on the `info@ukpolyamory.org` Workspace account. The script:

1. Searches the inbox for emails containing a `.ics` calendar attachment
2. Parses the ICS content to extract event details
3. Adds, updates, or deletes the event on the community calendar via the Google Calendar API
4. Labels and archives the processed email

This avoids all forwarding verification issues by using the Calendar API directly rather than email.

## Infrastructure

- **Domain DNS:** Cloudflare
- **MX records:** Google (Workspace)
- **Google Workspace account:** info@ukpolyamory.org (admin access required to set up script)
- **Script location:** Google Apps Script, tied to info@ukpolyamory.org
- **Calendar ID:** `c_88c790511d359402115e8138d94d312ae1a5943df7f1cc155dc5f4c584fb7725@group.calendar.google.com`

## What the Script Handles

- Timed events (with correct Europe/London timezone handling)
- All-day events
- Recurring events (RRULE, EXDATE, RDATE)
- Event updates (finds existing event by UID and updates rather than duplicating)
- Event cancellations (deletes the event from the calendar)
- Google Meet links (extracted from `X-GOOGLE-CONFERENCE` field)
- Organiser and attendee information (appended to description)
- Location
- Event URL
- Status
- Strips Google boilerplate from descriptions

## Setup Instructions

### 1. Find the Calendar ID

1. Open Google Calendar as the account that owns the community calendar
2. Find the calendar in the left sidebar, click the three-dot menu
3. Select **Settings and sharing**
4. Scroll to **Integrate calendar** — copy the **Calendar ID**

### 2. Set Up the Script

1. Go to [script.google.com](https://script.google.com) signed in as `info@ukpolyamory.org`
2. Click **New project** and name it (e.g. "Calendar forward")
3. Delete the default `myFunction` and paste in the full script below
4. Click **Services** (+ icon in left sidebar) and add **Google Calendar API**
5. Save the script (Ctrl+S)
6. Click **Run** once manually to trigger the permissions/authorisation flow
7. Accept the permissions Google requests

### 3. Set Up the Timer

1. Click the **clock icon** (Triggers) in the left sidebar
2. Click **Add Trigger** (bottom right)
3. Configure:
   - **Function:** `forwardCalendarInvites`
   - **Event source:** Time-driven
   - **Type:** Minutes timer
   - **Interval:** Every 5 minutes
4. Click Save

The script will now run automatically every 5 minutes.

### 4. Monitoring

- **Executions log** (play button icon in left sidebar) — shows all runs and any errors
- **Triggers screen** — confirms the timer is active
- Processed emails are labelled `forwarded-to-calendar` and archived

## Notes

- There is up to a 5-minute delay between an invite being sent and it appearing on the calendar, due to the polling interval.
- The script stores a `[[UID:...]]` tag at the top of each event description. This is used to find existing events when processing updates or cancellations. Do not manually remove this tag from events on the calendar.
- The **Deploy** button in Apps Script is not needed — the script runs privately on Google's servers via the timer trigger, no deployment required.
- Google Docs or other file attachments on calendar invites are not carried through — the Calendar API insert does not support file attachments directly.

## Full Script

```javascript
function forwardCalendarInvites() {
  const CALENDAR_ID = 'c_88c790511d359402115e8138d94d312ae1a5943df7f1cc155dc5f4c584fb7725@group.calendar.google.com';
  
  const threads = GmailApp.search('in:inbox has:attachment filename:invite.ics -label:forwarded-to-calendar');
  Logger.log('Threads found: ' + threads.length);
  
  threads.forEach((thread, threadIndex) => {
    Logger.log('Processing thread ' + threadIndex + ', messages: ' + thread.getMessages().length);
    const message = thread.getMessages()[0];
    const icsAttachments = message.getAttachments().filter(a => 
      a.getName().endsWith('.ics') || a.getContentType() === 'text/calendar'
    );
    Logger.log('ICS attachments found: ' + icsAttachments.length);
    
    icsAttachments.slice(0, 1).forEach(attachment => {
      const icsContent = attachment.getDataAsString().replace(/\r\n/g, '\n').replace(/\r/g, '\n');
      
      const method = (icsContent.match(/^METHOD:(.+)$/m) || [])[1] || 'REQUEST';
      Logger.log('Method: ' + method.trim());
      
      const veventMatch = icsContent.match(/BEGIN:VEVENT([\s\S]*?)END:VEVENT/);
      if (!veventMatch) {
        Logger.log('No VEVENT block found');
        return;
      }
      const vevent = veventMatch[1];
      
      const uid      = (vevent.match(/^UID:(.+)$/m) || [])[1] || '';
      const sequence = parseInt((vevent.match(/^SEQUENCE:(.+)$/m) || [])[1] || '0', 10);
      const summary  = (vevent.match(/^SUMMARY:(.+)$/m) || [])[1] || 'Untitled Event';
      const dtstart  = (vevent.match(/^DTSTART[^:]*:(.+)$/m) || [])[1];
      const dtend    = (vevent.match(/^DTEND[^:]*:(.+)$/m) || [])[1];
      const location = (vevent.match(/^LOCATION:(.+)$/m) || [])[1] || '';
      const meetLink = (vevent.match(/^X-GOOGLE-CONFERENCE:(.+)$/m) || [])[1] || '';
      const url      = (vevent.match(/^URL:(.+)$/m) || [])[1] || '';
      const status   = (vevent.match(/^STATUS:(.+)$/m) || [])[1] || '';
      
      const rrule  = (vevent.match(/^RRULE:(.+)$/m) || [])[1];
      const exdate = (vevent.match(/^EXDATE[^:]*:(.+)$/m) || [])[1];
      const rdate  = (vevent.match(/^RDATE[^:]*:(.+)$/m) || [])[1];
      
      const recurrence = [];
      if (rrule)  recurrence.push('RRULE:' + rrule.trim());
      if (exdate) recurrence.push('EXDATE:' + exdate.trim());
      if (rdate)  recurrence.push('RDATE:' + rdate.trim());
      
      Logger.log('UID: ' + uid.trim());
      Logger.log('Sequence: ' + sequence);
      Logger.log('Method: ' + method.trim());
      
      const organizerMatch = vevent.match(/^ORGANIZER;CN=([^:]+):mailto:(.+)$/m);
      const organizerName  = organizerMatch ? organizerMatch[1].trim() : '';
      const organizerEmail = organizerMatch ? organizerMatch[2].trim() : '';
      
      const attendeeMatches = [...vevent.matchAll(/^ATTENDEE[^:]*CN=([^;:]+)[^:]*:mailto:(.+)$/mg)];
      const attendees = attendeeMatches.map(m => `${m[1].trim()} <${m[2].trim()}>`);
      
      let descriptionParts = [];
      if (meetLink)             descriptionParts.push('Join with Google Meet: ' + meetLink);
      if (url)                  descriptionParts.push('URL: ' + url);
      if (status)               descriptionParts.push('Status: ' + status);
      if (organizerName)        descriptionParts.push('Organiser: ' + organizerName + ' <' + organizerEmail + '>');
      if (attendees.length > 0) descriptionParts.push('Attendees:\n' + attendees.map(a => '  ' + a).join('\n'));
      
      const rawDescription = (vevent.match(/^DESCRIPTION:(.+)$/m) || [])[1] || '';
      const cleanDescription = rawDescription
        .replace(/\\n/g, '\n')
        .replace(/-::~:~::.*?::~:~::-/gs, '')
        .trim();
      if (cleanDescription) descriptionParts.push(cleanDescription);
      
      const description = descriptionParts.join('\n\n');
      
      const existingEventId = findEventByUID(CALENDAR_ID, uid.trim());
      Logger.log('Existing event ID: ' + existingEventId);
      
      if (method.trim() === 'CANCEL') {
        if (existingEventId) {
          Calendar.Events.remove(CALENDAR_ID, existingEventId);
          Logger.log('Deleted event: ' + summary);
        } else {
          Logger.log('Cancel received but no matching event found for UID: ' + uid);
        }
      } else {
        if (dtstart && dtend) {
          const isAllDay = dtstart.trim().length === 8;
          
          let event;
          if (isAllDay) {
            const startDate = formatAllDayDate(dtstart.trim());
            const endDate   = formatAllDayDate(dtend.trim());
            Logger.log('All-day event: ' + startDate + ' to ' + endDate);
            event = {
              summary: summary.trim(),
              description: '[[UID:' + uid.trim() + ']]\n\n' + description,
              location: location.trim(),
              start: { date: startDate },
              end: { date: endDate }
            };
          } else {
            const start = parseICSLocalDate(dtstart.trim());
            const end   = parseICSLocalDate(dtend.trim());
            Logger.log('Timed event: ' + start + ' to ' + end);
            event = {
              summary: summary.trim(),
              description: '[[UID:' + uid.trim() + ']]\n\n' + description,
              location: location.trim(),
              start: { dateTime: start, timeZone: 'Europe/London' },
              end: { dateTime: end, timeZone: 'Europe/London' }
            };
          }
          
          if (recurrence.length > 0) {
            event.recurrence = recurrence;
          }
          
          if (existingEventId) {
            Logger.log('Updating existing event: ' + existingEventId);
            Calendar.Events.update(event, CALENDAR_ID, existingEventId);
            Logger.log('Updated event: ' + summary);
          } else {
            Logger.log('Inserting new event');
            Calendar.Events.insert(event, CALENDAR_ID);
            Logger.log('Inserted event: ' + summary);
          }
        } else {
          Logger.log('Could not parse DTSTART or DTEND');
        }
      }
    });
    
    thread.addLabel(GmailApp.createLabel('forwarded-to-calendar'));
    thread.moveToArchive();
  });
}

function findEventByUID(calendarId, uid) {
  Logger.log('Searching for UID: "' + uid + '"');
  try {
    const results = Calendar.Events.list(calendarId, {
      q: '[[UID:' + uid + ']]',
      maxResults: 10
    });
    Logger.log('Search returned ' + (results.items ? results.items.length : 0) + ' results');
    if (results.items && results.items.length > 0) {
      results.items.forEach(item => Logger.log('Found: id="' + item.id + '" summary="' + item.summary + '"'));
      return results.items[0].id;
    }
  } catch(e) {
    Logger.log('Error in findEventByUID: ' + e);
  }
  return null;
}

function formatAllDayDate(dtString) {
  return dtString.substr(0, 4) + '-' + dtString.substr(4, 2) + '-' + dtString.substr(6, 2);
}

function parseICSLocalDate(dtString) {
  const clean = dtString.replace('Z', '').trim();
  const year  = clean.substr(0, 4);
  const month = clean.substr(4, 2);
  const day   = clean.substr(6, 2);
  const hour  = clean.substr(9, 2);
  const min   = clean.substr(11, 2);
  const sec   = clean.substr(13, 2) || '00';
  const result = `${year}-${month}-${day}T${hour}:${min}:${sec}`;
  Logger.log('Local datetime string: ' + result);
  return result;
}
```

## Known Limitations

- Up to 5-minute delay on new invites appearing
- Google Docs/file attachments on invites are not carried through
- Recurring event exceptions (edits to single instances of a recurring event) are not handled — the whole series will be updated instead
- If the `[[UID:...]]` tag is manually removed from an event description, updates and cancellations for that event will no longer work
- Script runs in the context of `info@ukpolyamory.org` — if that account is deleted or loses Workspace access the script will stop working

## Maintenance

If the script stops working, check:

1. **Executions log** in Apps Script for errors
2. **Triggers screen** to confirm the timer is still active — occasionally Google deactivates triggers on scripts that haven't been run manually for a long time
3. The `info@ukpolyamory.org` account still has an active Workspace licence
4. The Google Calendar API is still enabled under Services in the script editor
