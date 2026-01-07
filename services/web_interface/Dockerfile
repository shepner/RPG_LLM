FROM nginx:alpine

# Copy web interface files
COPY services/web_interface/src/ /usr/share/nginx/html/

# Generate build timestamp and create version file at build time
# This will be unique for each container build
RUN BUILD_TIME=$(date -u +"%Y%m%d-%H%M%S") && \
    echo "window.BUILD_VERSION = '${BUILD_TIME}';" > /usr/share/nginx/html/version.js

# Expose port
EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]

