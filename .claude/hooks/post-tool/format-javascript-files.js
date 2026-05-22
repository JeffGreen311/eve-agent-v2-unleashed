#!/usr/bin/env node

// JavaScript Formatting Hook
// This hook automatically formats JavaScript files after they are created or modified

const fs = require('fs');
const path = require('path');
const { execSync } = require('child_process');

console.log('JavaScript Formatting Hook: Starting...');

// Get the file that was modified/created
const filePath = process.argv[2];

if (!filePath) {
  console.log('No file path provided. Checking recently modified JavaScript files...');
  
  // If no file path provided, check recent JavaScript files in common directories
  const checkDirs = ['src', 'lib', 'scripts', 'tools'];
  const jsFiles = [];
  
  checkDirs.forEach(dir => {
    if (fs.existsSync(dir)) {
      const files = fs.readdirSync(dir);
      files.forEach(file => {
        if (file.endsWith('.js') || file.endsWith('.jsx')) {
          jsFiles.push(path.join(dir, file));
        }
      });
    }
  });
  
  jsFiles.forEach(file => {
    try {
      console.log(`Formatting ${file}...`);
      execSync(`prettier --write "${file}"`, { stdio: 'inherit' });
    } catch (error) {
      console.error(`Error formatting ${file}:`, error.message);
    }
  });
} else if (filePath.endsWith('.js') || filePath.endsWith('.jsx')) {
  // Format the specific file
  try {
    console.log(`Formatting ${filePath}...`);
    execSync(`prettier --write "${filePath}"`, { stdio: 'inherit' });
    console.log('Formatting complete!');
  } catch (error) {
    console.error('Error formatting file:', error.message);
  }
} else {
  console.log('File is not a JavaScript file. Skipping formatting.');
}

console.log('JavaScript Formatting Hook: Finished.');