import os
import sys
import argparse
import smtplib
from datetime import datetime, timedelta
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

import psycopg2
from psycopg2.extras import RealDictCursor
from flask import Flask, render_template
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)

# Configuration
DATABASE_URL = os.getenv('DATABASE_URL')
NOTIFICATION_FOLLOW_UP_HOURS = int(os.getenv('NOTIFICATION_FOLLOW_UP_HOURS', 24))
MAIL_SERVER = os.getenv('MAIL_SERVER')
MAIL_PORT = int(os.getenv('MAIL_PORT', 587))
MAIL_USERNAME = os.getenv('MAIL_USERNAME')
MAIL_PASSWORD = os.getenv('MAIL_PASSWORD')
MAIL_USE_TLS = os.getenv('MAIL_USE_TLS', 'True').lower() == 'true'


def get_db_connection():
    """Get database connection"""
    return psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)


def create_notification_table():
    """Create the notification table if it doesn't exist"""
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            # Check if table exists
            cur.execute("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_name = 'notification'
                ) as table_exists;
            """)
            result = cur.fetchone()
            table_exists = result['table_exists']
            
            if not table_exists:
                # Create table with CASCADE foreign key
                cur.execute("""
                    CREATE TABLE notification (
                        id SERIAL PRIMARY KEY,
                        user_id INTEGER NOT NULL REFERENCES "user"(id),
                        match_id INTEGER NOT NULL REFERENCES match(id) ON DELETE CASCADE,
                        notification_type VARCHAR(50) NOT NULL,
                        sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        email_sent BOOLEAN DEFAULT FALSE,
                        next_email_time TIMESTAMP,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        UNIQUE(user_id, match_id)
                    );
                """)
            else:
                # Update existing foreign key constraint to CASCADE if needed
                cur.execute("""
                    DO $$ 
                    BEGIN
                        -- Drop existing foreign key constraint if it exists
                        IF EXISTS (
                            SELECT 1 FROM pg_constraint 
                            WHERE conname = 'notification_match_id_fkey'
                        ) THEN
                            ALTER TABLE notification DROP CONSTRAINT notification_match_id_fkey;
                        END IF;
                        
                        -- Add new foreign key constraint with CASCADE
                        ALTER TABLE notification 
                        ADD CONSTRAINT notification_match_id_fkey 
                        FOREIGN KEY (match_id) REFERENCES match(id) ON DELETE CASCADE;
                        
                        -- Add unique constraint if it doesn't exist
                        IF NOT EXISTS (
                            SELECT 1 FROM pg_constraint 
                            WHERE conname = 'notification_user_match_unique'
                        ) THEN
                            ALTER TABLE notification 
                            ADD CONSTRAINT notification_user_match_unique UNIQUE (user_id, match_id);
                        END IF;
                    END $$;
                """)
            
            # Create indexes
            cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_notification_user_id ON notification(user_id);
                CREATE INDEX IF NOT EXISTS idx_notification_match_id ON notification(match_id);
                CREATE INDEX IF NOT EXISTS idx_notification_next_email_time ON notification(next_email_time);
            """)
            conn.commit()
    finally:
        conn.close()


def cleanup_notifications():
    """Clean up notifications for deleted or completed matches"""
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            # Remove notifications for matches that no longer exist or are completed/declined
            cur.execute("""
                DELETE FROM notification 
                WHERE match_id NOT IN (SELECT id FROM match) 
                   OR match_id IN (
                       SELECT id FROM match 
                       WHERE status IN ('complete', 'completed', 'contracted', 'declined')
                   )
            """)
            deleted_count = cur.rowcount
            conn.commit()
            return deleted_count
    finally:
        conn.close()


def get_users_with_new_activity():
    """Get users who have matches with 'matched', 'selected', or 'applied' status"""
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            # Get influencers with new activity (exclude 'applied' since that's their own action)
            cur.execute("""
                SELECT DISTINCT
                    i.user_id,
                    u.email,
                    i.name as user_name,
                    i.id as influencer_id,
                    COUNT(m.id) as activity_count,
                    'influencer' as user_type,
                    FALSE as has_applications
                FROM match m
                JOIN influencer i ON m.influencer_id = i.id
                JOIN "user" u ON i.user_id = u.id
                WHERE m.status IN ('matched', 'selected')
                  AND u.is_active = true
                  AND u.is_verified = true
                GROUP BY i.user_id, u.email, i.name, i.id
            """)
            influencers = cur.fetchall()
            
            # Get brands with new activity, check if they have applications
            cur.execute("""
                SELECT DISTINCT
                    b.user_id,
                    u.email,
                    b.company_name as user_name,
                    b.id as brand_id,
                    COUNT(m.id) as activity_count,
                    'brand' as user_type,
                    BOOL_OR(m.status = 'applied') as has_applications
                FROM match m
                JOIN campaign c ON m.campaign_id = c.id
                JOIN brand b ON c.brand_id = b.id
                JOIN "user" u ON b.user_id = u.id
                WHERE m.status IN ('matched', 'selected', 'applied')
                  AND u.is_active = true
                  AND u.is_verified = true
                GROUP BY b.user_id, u.email, b.company_name, b.id
            """)
            brands = cur.fetchall()
            
            return list(influencers) + list(brands)
    finally:
        conn.close()


def should_send_notification(user_id, match_ids):
    """Check if we should send a notification to this user for these matches"""
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            # Check if there are already notifications for any of these matches for this user
            # that are still within the follow-up window (next_email_time > current time)
            placeholders = ','.join(['%s'] * len(match_ids))
            cur.execute(f"""
                SELECT COUNT(*) as count
                FROM notification
                WHERE user_id = %s 
                  AND match_id IN ({placeholders})
                  AND next_email_time > CURRENT_TIMESTAMP
            """, [user_id] + match_ids)
            
            result = cur.fetchone()
            # Send notification if no recent notifications exist OR if follow-up time has passed
            return result['count'] == 0
    finally:
        conn.close()


def get_user_matches_for_notification(user_id):
    """Get the specific matches that need notifications for a user"""
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            # Get matches for influencers (exclude 'applied' since that's their own action)
            cur.execute("""
                SELECT m.id as match_id, m.status, 'influencer' as user_type
                FROM match m
                JOIN influencer i ON m.influencer_id = i.id
                WHERE i.user_id = %s 
                  AND m.status IN ('matched', 'selected')
            """, (user_id,))
            influencer_matches = cur.fetchall()
            
            # Get matches for brands (include all statuses)
            cur.execute("""
                SELECT m.id as match_id, m.status, 'brand' as user_type
                FROM match m
                JOIN campaign c ON m.campaign_id = c.id
                JOIN brand b ON c.brand_id = b.id
                WHERE b.user_id = %s 
                  AND m.status IN ('matched', 'selected', 'applied')
            """, (user_id,))
            brand_matches = cur.fetchall()
            
            return list(influencer_matches) + list(brand_matches)
    finally:
        conn.close()


def send_notification_email(email, user_name, activity_count, has_applications=False, dry_run=False):
    """Send notification email to user"""
    if dry_run:
        print(f"DRY RUN: Would send email to {email} ({user_name}) - {activity_count} new activities")
        return True
    
    try:
        if has_applications:
            message_text = f"You have {activity_count} new application{'s' if activity_count > 1 else ''} from influencers waiting for your review!"
        else:
            message_text = f"You have {activity_count} new match{'es' if activity_count > 1 else ''} waiting for your attention!"
        
        with app.app_context():
            html_content = render_template('generic_notification.html',
                                         user_name=user_name,
                                         message=message_text,
                                         dashboard_url="https://www.collablab.net/dashboard")
        
        print(f"SMTP Config Check:")
        print(f"  Server: {MAIL_SERVER}")
        print(f"  Port: {MAIL_PORT}")
        print(f"  TLS: {MAIL_USE_TLS}")
        print(f"  Username: {MAIL_USERNAME[:5]}***")  # Only show first 5 chars
        
        msg = MIMEMultipart('alternative')
        msg['Subject'] = "New Activity on CollabLab"
        msg['From'] = MAIL_USERNAME
        msg['To'] = email
        
        html_part = MIMEText(html_content, 'html')
        msg.attach(html_part)
        
        server = smtplib.SMTP(MAIL_SERVER, MAIL_PORT)
        if MAIL_USE_TLS:
            server.starttls()
        server.login(MAIL_USERNAME, MAIL_PASSWORD)
        server.send_message(msg)
        server.quit()
        
        return True
    except Exception as e:
        print(f"Error sending email to {email}: {str(e)}")
        return False


def create_notification_record(user_id, match_id, notification_type):
    """Create or update a notification record in the database"""
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            next_email_time = datetime.now() + timedelta(hours=NOTIFICATION_FOLLOW_UP_HOURS)
            
            # Use UPSERT to either insert new record or update existing one
            cur.execute("""
                INSERT INTO notification (user_id, match_id, notification_type, email_sent, next_email_time, sent_at)
                VALUES (%s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
                ON CONFLICT ON CONSTRAINT notification_user_match_unique
                DO UPDATE SET 
                    email_sent = EXCLUDED.email_sent,
                    next_email_time = EXCLUDED.next_email_time,
                    sent_at = CURRENT_TIMESTAMP,
                    notification_type = EXCLUDED.notification_type
            """, (user_id, match_id, notification_type, True, next_email_time))
            conn.commit()
    finally:
        conn.close()


def process_notifications(dry_run=False):
    """Main function to process and send notifications"""
    print(f"{'DRY RUN: ' if dry_run else ''}Starting notification processing...")
    
    # First, clean up old notifications
    deleted_count = cleanup_notifications()
    print(f"Cleaned up {deleted_count} notifications for deleted/completed matches")
    
    # Get users with new activity
    users_with_activity = get_users_with_new_activity()
    print(f"Found {len(users_with_activity)} users with potential new activity")
    
    sent_count = 0
    
    for user_data in users_with_activity:
        user_id = user_data['user_id']
        email = user_data['email']
        user_name = user_data['user_name']
        activity_count = user_data['activity_count']
        
        # Get specific matches for this user
        user_matches = get_user_matches_for_notification(user_id)
        match_ids = [match['match_id'] for match in user_matches]
        
        # Get has_applications flag
        has_applications = user_data.get('has_applications', False)
        
        # Check if we should send notification
        if should_send_notification(user_id, match_ids):
            # Send email
            email_sent = send_notification_email(email, user_name, activity_count, has_applications, dry_run)
            
            if email_sent:
                # Create notification records for each match
                for match in user_matches:
                    if not dry_run:
                        create_notification_record(
                            user_id, 
                            match['match_id'], 
                            f"new_activity_{match['status']}"
                        )
                sent_count += 1
                print(f"{'DRY RUN: ' if dry_run else ''}Sent notification to {email} ({user_name})")
        else:
            print(f"Skipping {email} ({user_name}) - already has recent notifications")
    
    print(f"{'DRY RUN: ' if dry_run else ''}Processing complete. {sent_count} notifications sent.")
    return sent_count


def main():
    """Main function to run notification processing"""
    parser = argparse.ArgumentParser(description='Process notification emails')
    parser.add_argument('--dry-run', action='store_true', 
                       help='Run in dry-run mode (no emails sent)')
    
    args = parser.parse_args()
    
    try:
        print("Creating notification table...")
        create_notification_table()
        print("Processing notifications...")
        sent_count = process_notifications(dry_run=args.dry_run)
        
        if args.dry_run:
            print(f"Dry run complete. Would have sent {sent_count} emails.")
        else:
            print(f"Processing complete. {sent_count} emails sent.")
            
    except Exception as e:
        print(f"Error: {str(e)}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()