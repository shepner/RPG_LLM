FROM nginx:alpine

# Generate build timestamp and create version file
RUN BUILD_TIME=$(date -u +"%Y%m%d-%H%M%S") && \
    echo "window.BUILD_VERSION = '${BUILD_TIME}';" > /tmp/version.js

# Copy web interface files
COPY services/web_interface/src/ /usr/share/nginx/html/

# Copy version file
COPY /tmp/version.js /usr/share/nginx/html/version.js

# Expose port
EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]

