"""Run existing operator commands against hosted storage without shell history secrets."""
import getpass
import os
import sys

if __name__=='__main__':
    if not os.getenv('DATABASE_URL'):
        if not sys.stdin.isatty():
            sys.exit('Set DATABASE_URL securely, or run from an interactive terminal.')
        os.environ['DATABASE_URL']=getpass.getpass('Supabase PostgreSQL connection URL (hidden): ')
    import app
    from fastapi import HTTPException
    try:
        app.operator()
    except HTTPException as error:
        sys.exit(error.detail)
    except Exception:
        sys.exit('Operator action failed. Check database access and try again; no credentials printed.')
