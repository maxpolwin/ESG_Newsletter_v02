#!/usr/bin/env python3
"""
Content Storage System

This module provides persistent storage for all identified content across different sources
(RSS, Email, Academic) using SQLite. It's designed to be compatible with PythonAnywhere.

Author: Max Polwin
"""

import os
import sqlite3
import json
import logging
from datetime import datetime
from config import CACHE_DIR

# Database file path
DB_FILE = os.path.join(CACHE_DIR, "content_database.db")

def get_db_connection():
    """
    Create a database connection and return it.
    Creates the database and tables if they don't exist.
    """
    try:
        conn = sqlite3.connect(DB_FILE)
        conn.row_factory = sqlite3.Row  # This enables column access by name
        
        # Create tables if they don't exist
        with conn:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS content (
                    id TEXT PRIMARY KEY,
                    source_type TEXT NOT NULL,
                    title TEXT NOT NULL,
                    content TEXT,
                    url TEXT,
                    date_added TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    date_published TIMESTAMP,
                    source_info TEXT,
                    keywords TEXT,
                    metadata TEXT,
                    status TEXT DEFAULT 'active'
                )
            ''')
            
            # Create index for faster searches
            conn.execute('''
                CREATE INDEX IF NOT EXISTS idx_content_source_type 
                ON content(source_type)
            ''')
            conn.execute('''
                CREATE INDEX IF NOT EXISTS idx_content_date_published 
                ON content(date_published)
            ''')
            
        return conn
    except Exception as e:
        logging.error(f"Error creating database connection: {e}")
        raise

def store_content(content_item):
    """
    Store a content item in the database.
    
    Args:
        content_item (dict): The content item to store with all its metadata
        
    Returns:
        bool: True if successful, False otherwise
    """
    conn = None
    try:
        conn = get_db_connection()
        with conn:
            # Convert complex objects to JSON strings
            source_info = json.dumps(content_item.get('source_info', {}))
            keywords = json.dumps(content_item.get('keywords', []))
            metadata = json.dumps(content_item.get('metadata', {}))
            
            # Convert date_published to ISO format if it exists
            date_published = None
            if 'date_published' in content_item:
                if isinstance(content_item['date_published'], (int, float)):
                    date_published = datetime.fromtimestamp(content_item['date_published']).isoformat()
                else:
                    date_published = content_item['date_published']
            
            conn.execute('''
                INSERT OR REPLACE INTO content 
                (id, source_type, title, content, url, date_published, 
                 source_info, keywords, metadata)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                content_item.get('id'),
                content_item.get('source_type'),
                content_item.get('title'),
                content_item.get('content'),
                content_item.get('url'),
                date_published,
                source_info,
                keywords,
                metadata
            ))
            
        logging.info(f"Successfully stored content item: {content_item.get('title')}")
        return True
    except Exception as e:
        logging.error(f"Error storing content item: {e}")
        return False
    finally:
        if conn:
            conn.close()

def get_content_by_id(content_id):
    """
    Retrieve a content item by its ID.
    
    Args:
        content_id (str): The ID of the content item to retrieve
        
    Returns:
        dict: The content item if found, None otherwise
    """
    conn = None
    try:
        conn = get_db_connection()
        with conn:
            cursor = conn.execute('SELECT * FROM content WHERE id = ?', (content_id,))
            row = cursor.fetchone()
            
            if row:
                return dict(row)
            return None
    except Exception as e:
        logging.error(f"Error retrieving content item: {e}")
        return None
    finally:
        if conn:
            conn.close()

def get_content_by_source(source_type, limit=100, offset=0):
    """
    Retrieve content items by source type.
    
    Args:
        source_type (str): The type of source (e.g., 'rss', 'email', 'academic')
        limit (int): Maximum number of items to return
        offset (int): Number of items to skip
        
    Returns:
        list: List of content items
    """
    conn = None
    try:
        conn = get_db_connection()
        with conn:
            cursor = conn.execute('''
                SELECT * FROM content 
                WHERE source_type = ? 
                ORDER BY date_published DESC 
                LIMIT ? OFFSET ?
            ''', (source_type, limit, offset))
            
            return [dict(row) for row in cursor.fetchall()]
    except Exception as e:
        logging.error(f"Error retrieving content by source: {e}")
        return []
    finally:
        if conn:
            conn.close()

def search_content(query, source_type=None, limit=100, offset=0):
    """
    Search content items by query string.
    
    Args:
        query (str): The search query
        source_type (str): Optional source type filter
        limit (int): Maximum number of items to return
        offset (int): Number of items to skip
        
    Returns:
        list: List of matching content items
    """
    conn = None
    try:
        conn = get_db_connection()
        with conn:
            if source_type:
                cursor = conn.execute('''
                    SELECT * FROM content 
                    WHERE (title LIKE ? OR content LIKE ?) 
                    AND source_type = ?
                    ORDER BY date_published DESC 
                    LIMIT ? OFFSET ?
                ''', (f'%{query}%', f'%{query}%', source_type, limit, offset))
            else:
                cursor = conn.execute('''
                    SELECT * FROM content 
                    WHERE title LIKE ? OR content LIKE ?
                    ORDER BY date_published DESC 
                    LIMIT ? OFFSET ?
                ''', (f'%{query}%', f'%{query}%', limit, offset))
            
            return [dict(row) for row in cursor.fetchall()]
    except Exception as e:
        logging.error(f"Error searching content: {e}")
        return []
    finally:
        if conn:
            conn.close()

def update_content_status(content_id, status):
    """
    Update the status of a content item.
    
    Args:
        content_id (str): The ID of the content item
        status (str): The new status
        
    Returns:
        bool: True if successful, False otherwise
    """
    conn = None
    try:
        conn = get_db_connection()
        with conn:
            conn.execute('''
                UPDATE content 
                SET status = ? 
                WHERE id = ?
            ''', (status, content_id))
            
        logging.info(f"Updated status for content item {content_id} to {status}")
        return True
    except Exception as e:
        logging.error(f"Error updating content status: {e}")
        return False
    finally:
        if conn:
            conn.close()

def cleanup_old_content(days=30):
    """
    Archive content items older than specified days.
    
    Args:
        days (int): Number of days after which content should be archived
        
    Returns:
        int: Number of items archived
    """
    conn = None
    try:
        conn = get_db_connection()
        with conn:
            cursor = conn.execute('''
                UPDATE content 
                SET status = 'archived' 
                WHERE date_published < datetime('now', ?)
            ''', (f'-{days} days',))
            
            archived_count = cursor.rowcount
            logging.info(f"Archived {archived_count} old content items")
            return archived_count
    except Exception as e:
        logging.error(f"Error cleaning up old content: {e}")
        return 0
    finally:
        if conn:
            conn.close()

def get_content_stats():
    """
    Get statistics about stored content.
    
    Returns:
        dict: Statistics about the content
    """
    conn = None
    try:
        conn = get_db_connection()
        with conn:
            stats = {}
            
            # Total content count
            cursor = conn.execute('SELECT COUNT(*) FROM content')
            stats['total'] = cursor.fetchone()[0]
            
            # Count by source type
            cursor = conn.execute('''
                SELECT source_type, COUNT(*) 
                FROM content 
                GROUP BY source_type
            ''')
            stats['by_source'] = dict(cursor.fetchall())
            
            # Count by status
            cursor = conn.execute('''
                SELECT status, COUNT(*) 
                FROM content 
                GROUP BY status
            ''')
            stats['by_status'] = dict(cursor.fetchall())
            
            return stats
    except Exception as e:
        logging.error(f"Error getting content stats: {e}")
        return {}
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    
    # Test the module
    test_content = {
        'id': 'test123',
        'source_type': 'test',
        'title': 'Test Content',
        'content': 'This is a test content item',
        'url': 'http://example.com/test',
        'date_published': datetime.now().isoformat(),
        'source_info': {'name': 'Test Source'},
        'keywords': ['test', 'example'],
        'metadata': {'test': True}
    }
    
    # Test storing content
    if store_content(test_content):
        print("Successfully stored test content")
        
        # Test retrieving content
        retrieved = get_content_by_id('test123')
        if retrieved:
            print(f"Retrieved content: {retrieved['title']}")
            
        # Test getting stats
        stats = get_content_stats()
        print(f"Content stats: {stats}") 