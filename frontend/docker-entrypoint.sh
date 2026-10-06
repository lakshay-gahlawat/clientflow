#!/bin/sh
set -e
export PORT="${PORT:-80}"
export API_UPSTREAM="${API_UPSTREAM:-http://backend:8000}"
case "$API_UPSTREAM" in
  http://*|https://*) ;;
  *) API_UPSTREAM="http://$API_UPSTREAM" ;;
esac
export API_UPSTREAM
envsubst '${PORT} ${API_UPSTREAM}' < /etc/nginx/templates/default.conf.template > /etc/nginx/conf.d/default.conf
exec nginx -g "daemon off;"
