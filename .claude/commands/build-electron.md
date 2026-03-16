---
description: Build and package Electron desktop app
---

# Electron Build and Package

Building the ImageTagger desktop application with Electron.

---

## Pre-Build Checks

### 1. Node Dependencies

!`npm list --depth=0 2>&1 | head -20`

### 2. Python Dependencies

!`pip list | grep -E "Flask|Pillow|watchdog"`

### 3. Electron Version

!`npx electron --version 2>/dev/null || echo "Electron not installed"`

---

## Build Steps

### Step 1: Install/Update Dependencies

!`npm install`

### Step 2: Test Flask Backend

!`timeout 3 python3 app.py 2>&1 | head -10 || echo "Flask check complete"`

### Step 3: Build Electron App

!`npm run build 2>&1 | tail -30`

---

## Platform-Specific Packaging

### Current Platform

!`uname -s`

### Package for Distribution

Choose packaging option:

#### macOS (DMG)
!`npm run dist -- --mac 2>&1 | tail -30`

#### Windows (NSIS Installer)
!`npm run dist -- --win 2>&1 | tail -30`

#### Linux (AppImage)
!`npm run dist -- --linux 2>&1 | tail -30`

---

## Build Artifacts

!`ls -lh dist/ 2>/dev/null | head -20 || echo "No dist folder found"`

---

## Post-Build Verification

### 1. Check Package Size

!`du -sh dist/*.dmg dist/*.exe dist/*.AppImage 2>/dev/null || echo "Check dist/ folder"`

### 2. Verify Electron Files

!`ls -lh electron/ 2>/dev/null`

### 3. Test Packaged App (Manual)

**macOS**: Open `dist/ImageTagger.dmg` and test the app
**Windows**: Run `dist/ImageTagger Setup.exe`
**Linux**: Run `dist/ImageTagger.AppImage`

---

## Common Build Issues

### Issue: Node Modules Missing
**Solution**:
!`rm -rf node_modules package-lock.json && npm install`

### Issue: Electron Builder Fails
**Solution**: Check electron-builder.json configuration
!`cat electron-builder.json 2>/dev/null || cat package.json | grep -A 20 "\"build\""`

### Issue: Python Not Found in Packaged App
**Solution**: Ensure Python is bundled correctly
- Check electron-builder configuration
- Verify python executable is in resources

### Issue: Large Package Size
**Solution**: Exclude unnecessary files
!`cat .gitignore`

---

## Build Configuration

### package.json Build Settings

!`cat package.json | grep -A 30 "\"build\""`

### Electron Builder Config

!`cat electron-builder.json 2>/dev/null || echo "Using package.json build config"`

---

## Distribution Checklist

Before distributing the app:

- [ ] Version number updated in package.json
- [ ] CHANGELOG.md updated
- [ ] All tests pass
- [ ] App tested on target platform
- [ ] Code signing (for macOS/Windows)
- [ ] README.md includes installation instructions
- [ ] License file included
- [ ] Build artifacts uploaded to release page

---

## Upload Release (if ready)

### Create GitHub Release

!`gh release create v$(node -p "require('./package.json').version") dist/*.dmg dist/*.exe dist/*.AppImage --title "Release v$(node -p "require('./package.json').version")" --notes "Release notes here" 2>/dev/null || echo "Use 'gh release create' to upload"`

---

## Build Complete!

Check the `dist/` folder for the packaged application.

### Next Steps:
1. Test the packaged app on target platform
2. Verify all features work correctly
3. Create release notes
4. Upload to GitHub releases or distribution platform
5. Update documentation with installation instructions

---

**Build Info:**
- Platform: !`uname -s`
- Node Version: !`node --version`
- Electron Version: !`npx electron --version 2>/dev/null`
- Package Version: !`node -p "require('./package.json').version" 2>/dev/null`