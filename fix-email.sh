#!/bin/bash
WRONG_EMAIL="max.polwin@posteo.de"
NEW_EMAIL="49167820+maxpolwin@users.noreply.github.com"

git filter-branch --force --env-filter '
if [ "$GIT_COMMITTER_EMAIL" = "$WRONG_EMAIL" ]
then
    export GIT_COMMITTER_EMAIL="$NEW_EMAIL"
fi
if [ "$GIT_AUTHOR_EMAIL" = "$WRONG_EMAIL" ]
then
    export GIT_AUTHOR_EMAIL="$NEW_EMAIL"
fi
' --tag-name-filter cat -- --branches --tags

