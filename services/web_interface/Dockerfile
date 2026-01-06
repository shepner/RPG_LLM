FROM nginx:alpine

# Copy web interface files
COPY services/web_interface/src/ /usr/share/nginx/html/

# Expose port
EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]

