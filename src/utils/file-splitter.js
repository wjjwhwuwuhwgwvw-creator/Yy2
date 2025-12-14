import fs from 'fs';
import path from 'path';
import { spawn } from 'child_process';

const MAX_WHATSAPP_SIZE = 1 * 1024 * 1024 * 1024;
const TEMP_DIR = '/tmp/file_splits';

if (!fs.existsSync(TEMP_DIR)) {
    fs.mkdirSync(TEMP_DIR, { recursive: true });
}

export async function downloadWithAria2(url, filename) {
    const tempPath = path.join(TEMP_DIR, `${Date.now()}_${filename}`);
    
    return new Promise((resolve, reject) => {
        console.log(`[aria2] Downloading: ${filename}`);
        
        const aria2 = spawn('aria2c', [
            '-x', '16',
            '-s', '16',
            '-k', '1M',
            '--max-connection-per-server=16',
            '--min-split-size=1M',
            '--file-allocation=none',
            '--continue=true',
            '-d', path.dirname(tempPath),
            '-o', path.basename(tempPath),
            '--timeout=600',
            '--connect-timeout=60',
            '--max-tries=10',
            '--retry-wait=5',
            '--enable-http-pipelining=true',
            '--http-accept-gzip=true',
            '--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            '--referer=https://apkdone.com/',
            '--header=Accept: */*',
            '--header=Accept-Language: en-US,en;q=0.9',
            url
        ]);
        
        let lastProgress = '';
        
        aria2.stdout.on('data', (data) => {
            const output = data.toString();
            const progressMatch = output.match(/\[#\w+\s+[\d.]+\w+\/[\d.]+\w+\((\d+)%\)/);
            if (progressMatch && progressMatch[1] !== lastProgress) {
                lastProgress = progressMatch[1];
                console.log(`[aria2] Progress: ${lastProgress}%`);
            }
        });
        
        aria2.stderr.on('data', (data) => {
            console.log(`[aria2] ${data.toString().trim()}`);
        });
        
        aria2.on('close', (code) => {
            if (code === 0 && fs.existsSync(tempPath)) {
                const size = fs.statSync(tempPath).size;
                console.log(`[aria2] Download complete: ${formatBytes(size)}`);
                resolve(tempPath);
            } else {
                reject(new Error(`aria2c exited with code ${code}`));
            }
        });
        
        aria2.on('error', (err) => {
            reject(err);
        });
    });
}

export async function getRemoteFileSize(url) {
    try {
        const response = await fetch(url, {
            method: 'HEAD',
            headers: {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
        });
        
        const contentLength = response.headers.get('content-length');
        return contentLength ? parseInt(contentLength) : null;
    } catch (error) {
        console.error('[FileSplitter] Error getting file size:', error.message);
        return null;
    }
}

export function needsSplitting(fileSize) {
    return fileSize && fileSize > MAX_WHATSAPP_SIZE;
}

export async function splitFile(filePath, chunkSize = MAX_WHATSAPP_SIZE) {
    const stats = fs.statSync(filePath);
    const fileSize = stats.size;
    const numParts = Math.ceil(fileSize / chunkSize);
    const parts = [];
    
    const baseName = path.basename(filePath);
    
    console.log(`[FileSplitter] Splitting ${formatBytes(fileSize)} into ${numParts} parts...`);
    
    const chunkSizeInt = Math.floor(chunkSize);
    
    for (let i = 0; i < numParts; i++) {
        const partPath = path.join(TEMP_DIR, `${baseName}.part${String(i + 1).padStart(3, '0')}`);
        const start = i * chunkSizeInt;
        const end = Math.min(start + chunkSizeInt, fileSize);
        const partSize = end - start;
        
        await new Promise((resolve, reject) => {
            const readStream = fs.createReadStream(filePath, { start, end: end - 1 });
            const writeStream = fs.createWriteStream(partPath);
            
            readStream.pipe(writeStream);
            
            writeStream.on('finish', () => {
                parts.push({
                    path: partPath,
                    partNumber: i + 1,
                    totalParts: numParts,
                    size: partSize,
                    originalName: baseName
                });
                console.log(`[FileSplitter] Part ${i + 1}/${numParts}: ${formatBytes(partSize)}`);
                resolve();
            });
            
            writeStream.on('error', reject);
            readStream.on('error', reject);
        });
    }
    
    return parts;
}

export async function splitFileFromUrl(url, filename, onProgress = null) {
    console.log(`[FileSplitter] Starting download: ${filename}`);
    
    const tempPath = await downloadWithAria2(url, filename);
    const stats = fs.statSync(tempPath);
    
    console.log(`[FileSplitter] File size: ${formatBytes(stats.size)}`);
    
    if (!needsSplitting(stats.size)) {
        return {
            needsSplit: false,
            filePath: tempPath,
            fileSize: stats.size
        };
    }
    
    console.log(`[FileSplitter] Splitting file...`);
    
    const parts = await splitFile(tempPath);
    
    try {
        fs.unlinkSync(tempPath);
    } catch (e) {
        console.log(`[FileSplitter] Could not delete temp file: ${e.message}`);
    }
    
    return {
        needsSplit: true,
        parts: parts,
        totalSize: stats.size,
        originalName: filename
    };
}

export function cleanupParts(parts) {
    for (const part of parts) {
        try {
            if (fs.existsSync(part.path)) {
                fs.unlinkSync(part.path);
            }
        } catch (e) {
            console.error(`[FileSplitter] Cleanup error: ${e.message}`);
        }
    }
}

export function getJoinInstructions(originalName, numParts) {
    // Generate list of all part names
    let partsList = '';
    for (let i = 1; i <= numParts; i++) {
        partsList += `   • ${originalName}.part${String(i).padStart(3, '0')}\n`;
    }
    
    return `📦 *تعليمات جمع الملف*

الملف الأصلي: *${originalName}*
عدد الأجزاء: *${numParts}*

📁 *أسماء الملفات:*
${partsList}
🔧 *طريقة الجمع باستخدام ZArchiver:*
1️⃣ حمّل جميع الأجزاء (${numParts} ملفات)
2️⃣ افتح تطبيق ZArchiver
3️⃣ انتقل إلى: Android/media/WhatsApp/Documents
4️⃣ اضغط مطولاً على الجزء الأول (.part001)
5️⃣ اختر "دمج الملفات" أو "Combine"
6️⃣ انتظر حتى يكتمل الدمج ✅

⚠️ *ملاحظة:* تأكد من تحميل جميع الأجزاء قبل الدمج

💡 إذا لم يكن لديك ZArchiver، أرسل "zarchiver" لتحميله`;
}

export function formatBytes(bytes, decimals = 2) {
    if (!bytes || bytes === 0) return "0 B";
    const k = 1024;
    const dm = decimals < 0 ? 0 : decimals;
    const sizes = ["B", "KB", "MB", "GB", "TB"];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return `${parseFloat((bytes / Math.pow(k, i)).toFixed(dm))} ${sizes[i]}`;
}

export { MAX_WHATSAPP_SIZE, TEMP_DIR };
