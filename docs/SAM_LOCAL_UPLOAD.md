# SafeSKU SAM Local bundle uploads

SAM Local is excellent for emulating the API Gateway-to-Lambda request path, but raw multipart/binary uploads can fail in the local proxy with a UTF-8 decode error. The SafeSKU UI therefore uses a local JSON/base64 chunk protocol when running in Build It mode.

The browser still selects one `.zip` bundle. SafeSKU splits it into 1 MiB chunks, sends each chunk as ASCII JSON, reassembles the ZIP locally, and then runs the normal manifest and checksum validation.

Cloud deployments use the separate S3 presigned upload path and do not use this workaround.
