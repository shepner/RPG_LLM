# Mattermost on ARM64 (Apple Silicon) Notes

## Platform Support

**Mattermost server is AMD64-only** - it does not have native ARM64 builds.

However, **Docker Desktop on Apple Silicon** can run AMD64 images using emulation (QEMU), which is what's happening in your setup.

## Current Status

✅ **Working**: Mattermost runs on ARM64 via Docker's platform emulation
⚠️ **Performance**: Slightly slower than native, but functional
⚠️ **Warning**: You'll see a platform mismatch warning in logs (this is normal)

## What You're Seeing

When Mattermost starts, you may see:
```
The requested image's platform (linux/amd64) does not match the detected host platform (linux/arm64/v8)
```

This is **expected and safe** - Docker is automatically using emulation to run the AMD64 image.

## Performance Considerations

- **CPU**: Slightly higher CPU usage due to emulation
- **Memory**: Similar memory usage
- **Startup**: May take a bit longer to start
- **Runtime**: Generally acceptable for development/testing

For production on ARM64, consider:
1. Running Mattermost on an AMD64 server
2. Using a cloud-hosted Mattermost instance
3. Waiting for official ARM64 support (if/when available)

## Configuration

The `docker-compose.yml` explicitly sets `platform: linux/amd64` to make the emulation explicit and avoid warnings.

## Alternatives

If performance is an issue, you could:
- Use a different chat platform with ARM64 support
- Run Mattermost in a VM with AMD64
- Use a cloud-hosted Mattermost instance

For most development/testing purposes, the emulated version works fine.
