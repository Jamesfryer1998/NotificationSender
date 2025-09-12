# NotificationSender

## Core Features

• Notification table with fields: user_id, match_id, notification_type, sent_at, email_sent, next_email_time
• Automatic cleanup - removes notifications for deleted/completed/contracted/declined matches
• Follow-up emails - sends repeat notifications every NOTIFICATION_FOLLOW_UP_HOURS (24h default)
• Duplicate prevention - unique constraint on user_id + match_id prevents spam

## Email Logic

• One email per influencer - groups by user to avoid multiple emails for same person
• Smart targeting - only sends to active & verified users
• Different messages for brands:
- Applications: "You have X new application(s) from influencers waiting for your review!"
- Regular matches: "You have X new match(es) waiting for your attention!"

## Status-Based Rules

• Influencers get notifications for: matched, selected (NOT applied - their own action)
• Brands get notifications for: matched, selected, applied (all statuses)
• Cleanup removes: complete, completed, contracted, declined matches

## CLI Interface

• Command line tool: python app.py (send emails) or python app.py --dry-run (test mode)
• Uses existing email config from .env file
• Uses generic_notification.html template with proper variables

Current Issue

• Foreign key constraint prevents campaign deletion - notifications table references match table without CASCADE delete


Notficiations

I am currently running a flask app with a postgres db on another service, this will connect to the postgres db, create the notification table if it needs to, the databse url is in .env. Going off the match table, check the match status. If a match has a matched, selected, applied status send a email to the users email (can be joined on brand or influencer to find user) giving them a notification about if they have new activtity. Use the templates/generic_notification.html. Create notification table with essential fields: user_id, match_id, notification_type, sent_at, email_sent, next_email_time. 

Rules:

- Do not interfere with any other the other tables, this table should be easy to delete and alter if I need to. 
- If a single influencer_id has multiple matches, we should only send 1 email.
- In the clean up task, check for deleted matches (i.e, not in the matches table anymore) or matches with status complete, completed, contracted. If we find any matching this criteria remove the relevent row from notification (run this first)
- When we add a notification row, add the next_email_time to the current time + NOTIFICATION_FOLLOW_UP_HOURS (can be found in env variables).
- Dont duplicate notifications
- Add a dry-run, this will allow me to test if we are sending to correct users, before I release. 


## Roll back plan

- Drop cron job
- Table snapshot of database?
- DROP TABLE IF EXISTS notification CASCADE;


TODO:
- Edit URL
    - if brand go to /dashboard/brand
    - if influencer go to /dashboard/influencer