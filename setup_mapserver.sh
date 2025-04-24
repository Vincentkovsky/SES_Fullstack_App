#!/bin/bash

# This script sets up MapServer with Apache

# Copy the configuration file to Apache's configuration directory
echo "Copying MapServer configuration to Apache..."
sudo cp mapserver.conf /private/etc/apache2/other/

# Enable required Apache modules
echo "Enabling required Apache modules..."
sudo sed -i '' 's/#LoadModule cgi_module/LoadModule cgi_module/' /private/etc/apache2/httpd.conf
sudo sed -i '' 's/#LoadModule headers_module/LoadModule headers_module/' /private/etc/apache2/httpd.conf

# Restart Apache
echo "Restarting Apache..."
sudo apachectl restart

echo "MapServer setup completed. You can now test the WMS service." 