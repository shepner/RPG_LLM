FROM nginx:alpine

# Copy web interface files
COPY src/ /usr/share/nginx/html/

# Expose port
EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]

