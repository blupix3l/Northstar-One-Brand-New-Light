"""
Background Renderer Module for NorthStar Browser
Centralizes all background rendering logic
"""

def _wrap_background_script(script: str) -> str:
    """Wrap a background script with DOM ready check, retries, and error handling."""
    return f"""
(function() {{
    function initBackground() {{
        var cv = document.getElementById('bg');
        if (!cv) {{
            // Try again soon if canvas isn't ready yet
            requestAnimationFrame(function() {{
                setTimeout(initBackground, 50);
            }});
            return;
        }}
        
        try {{
            {script}
        }} catch (e) {{
            console.error('Failed to initialize background:', e);
        }}
    }}
    
    // Run when DOM is ready, or immediately if already ready
    if (document.readyState === 'loading') {{
        document.addEventListener('DOMContentLoaded', initBackground);
    }} else {{
        // Also add a small delay to ensure everything is rendered
        setTimeout(initBackground, 10);
    }}
}})();
"""


def _get_classic_constellation_js(line_col, dot_col):
    """Classic constellation style with simple, clean look."""
    return f"""
    var W=cv.width=window.innerWidth, H=cv.height=window.innerHeight;
    var ctx=cv.getContext('2d');

    // Fixed seed for consistency across sessions
    var seed = 12345;
    function rand() {{
        seed = (seed * 9301 + 49297) % 233280;
        return seed / 233280;
    }}

    var N = Math.round(W * H / 18000);
    if (N < 30) N = 30; if (N > 70) N = 70;

    var pts=[];
    for (var i=0;i<N;i++) pts.push([rand()*W, rand()*H]);

    var THRESH = Math.min(W,H) * 0.18;

    ctx.lineWidth=0.5;
    for (var i=0;i<N;i++) {{
        for (var j=i+1;j<N;j++) {{
            var dx=pts[i][0]-pts[j][0], dy=pts[i][1]-pts[j][1];
            var dist=Math.sqrt(dx*dx+dy*dy);
            if (dist<THRESH) {{
                ctx.globalAlpha=(1-dist/THRESH)*0.12;
                ctx.strokeStyle='{line_col}';
                ctx.beginPath();
                ctx.moveTo(pts[i][0],pts[i][1]);
                ctx.lineTo(pts[j][0],pts[j][1]);
                ctx.stroke();
            }}
        }}
    }}

    for (var i=0;i<N;i++) {{
        var r=0.6+rand()*1.2;
        ctx.globalAlpha=0.2+rand()*0.35;
        ctx.fillStyle='{dot_col}';
        ctx.beginPath();
        ctx.arc(pts[i][0],pts[i][1],r,0,6.2832);
        ctx.fill();
    }}
"""


def _get_static_network_js(line_col, dot_col):
    """Static procedural network with geometric structure."""
    return f"""
    var W=cv.width=window.innerWidth, H=cv.height=window.innerHeight;
    var ctx=cv.getContext('2d');

    var seed = 98765;
    function rand() {{
        seed = (seed * 1103515245 + 12345) & 0x7fffffff;
        return seed / 0x7fffffff;
    }}

    var baseN = Math.round(W * H / 15000);
    var N = Math.min(Math.max(baseN, 40), 90);
    var pts=[];
    
    // Create some anchor points around the perimeter
    for (var i=0;i<6;i++) {{
        pts.push([rand()*W, rand()*H*0.15]);
        pts.push([rand()*W, H - rand()*H*0.15]);
        pts.push([rand()*W*0.15, rand()*H]);
        pts.push([W - rand()*W*0.15, rand()*H]);
    }}
    
    // Fill the rest with random points
    for (var i=pts.length;i<N;i++) {{
        pts.push([rand()*W, rand()*H]);
    }}

    var THRESH = Math.min(W,H) * 0.22;

    ctx.lineWidth=0.7;
    for (var i=0;i<pts.length;i++) {{
        for (var j=i+1;j<pts.length;j++) {{
            var dx=pts[i][0]-pts[j][0], dy=pts[i][1]-pts[j][1];
            var dist=Math.sqrt(dx*dx+dy*dy);
            if (dist<THRESH) {{
                ctx.globalAlpha=(1-dist/THRESH)*0.15;
                ctx.strokeStyle='{line_col}';
                ctx.beginPath();
                ctx.moveTo(pts[i][0],pts[i][1]);
                ctx.lineTo(pts[j][0],pts[j][1]);
                ctx.stroke();
            }}
        }}
    }}

    // Draw nodes - larger for perimeter anchors
    for (var i=0;i<pts.length;i++) {{
        var isAnchor = i < 24;
        var r = isAnchor ? 1.5 + rand()*1.0 : 0.7 + rand()*1.0;
        ctx.globalAlpha = isAnchor ? 0.45 + rand()*0.3 : 0.2 + rand()*0.3;
        ctx.fillStyle='{dot_col}';
        ctx.beginPath();
        ctx.arc(pts[i][0],pts[i][1],r,0,6.2832);
        ctx.fill();
    }}
"""


def _get_atmospheric_sky_js(line_col, dot_col, dark_mode):
    """Atmospheric sky with soft glow, depth, and subtle animations."""
    bg_grad = "rgba(8, 11, 20, 0)" if dark_mode else "rgba(240, 244, 255, 0)"
    accent_glow = "rgba(79, 195, 247, 0.04)" if dark_mode else "rgba(79, 70, 229, 0.03)"
    return f"""
    var W=cv.width=window.innerWidth, H=cv.height=window.innerHeight;
    var ctx=cv.getContext('2d');
    
    // Performance optimizations
    var isVisible = true;
    var animationId = null;
    var staticDrawn = false;
    
    // Handle page visibility to pause when not visible
    document.addEventListener('visibilitychange', function() {{
        isVisible = !document.hidden;
        if (isVisible && !animationId) {{
            draw();
        }}
    }});
    
    var startTime = Date.now();
    
    // Seeded RNG for static star positions
    var seed = 54321;
    function rand() {{
        seed = (seed * 1664525 + 1013904223) & 0x7fffffff;
        return seed / 0x7fffffff;
    }}
    
    // Create stars
    var stars = [];
    var N = Math.round(W * H / 18000); // Fewer stars for better performance
    if (N < 30) N = 30; if (N > 80) N = 80; // Reduced limits
    
    for (var i=0;i<N;i++) {{
        var x = rand() * W;
        var y = rand() * H;
        var size = rand() * 1.5 + 0.5;
        var brightness = rand() * 0.4 + 0.4; // Higher base brightness so they don't disappear
        var twinkleSpeed = rand() * 6000 + 4000; // Slower twinkling
        var twinkleOffset = rand() * Math.PI * 2;
        stars.push({{
            x: x, y: y,
            size: size,
            baseBrightness: brightness,
            twinkleSpeed: twinkleSpeed,
            twinkleOffset: twinkleOffset
        }});
    }}
    
    // Create shooting star
    var shootingStar = null;
    function maybeSpawnShootingStar() {{
        if (Math.random() < 0.0005 && !shootingStar) {{ // Less frequent shooting stars
            shootingStar = {{
                x: Math.random() * W,
                y: Math.random() * H * 0.3,
                length: Math.random() * 80 + 40,
                angle: Math.PI / 4 + Math.random() * 0.2,
                speed: Math.random() * 1.5 + 1, // Slower
                opacity: 1.0,
                life: 200 // Longer life
            }};
        }}
    }}
    
    // Draw a single static frame (gradient + stars, no animation loop)
    function renderStatic() {{
        ctx.clearRect(0, 0, W, H);
        var gradient = ctx.createRadialGradient(W/2, H/2, 0, W/2, H/2, Math.max(W, H)*0.7);
        gradient.addColorStop(0, '{accent_glow}');
        gradient.addColorStop(1, '{bg_grad}');
        ctx.fillStyle = gradient;
        ctx.fillRect(0, 0, W, H);
        for (var i=0;i<stars.length;i++) {{
            var star = stars[i];
            ctx.globalAlpha = star.baseBrightness;
            ctx.beginPath();
            ctx.arc(star.x, star.y, star.size, 0, Math.PI * 2);
            ctx.fillStyle='{dot_col}';
            ctx.fill();
        }}
    }}

    // Draw function (throttled to ~30fps; pauses when idle)
    var lastFrame = 0;
    var FRAME_INTERVAL = 33; // ms (~30fps) — smooth without burning GPU

    function draw(timestamp) {{
        if (!isVisible) {{
            animationId = null;
            return;
        }}

        var nowTs = timestamp || Date.now();
        if (nowTs - lastFrame < FRAME_INTERVAL) {{
            animationId = requestAnimationFrame(draw);
            return;
        }}
        lastFrame = nowTs;

        // Idle optimisation: if no shooting star is active, render the static
        // star field once (not every frame) to avoid continuous repaint.
        if (!shootingStar) {{
            maybeSpawnShootingStar();
            if (!shootingStar) {{
                if (!staticDrawn) {{
                    renderStatic();
                    staticDrawn = true;
                }}
                animationId = requestAnimationFrame(draw);
                return;
            }}
            staticDrawn = false;
        }}

        var now = Date.now();
        var elapsed = now - startTime;
        
        // Clear canvas
        ctx.clearRect(0, 0, W, H);
        
        // Soft background gradient (only draw once if it's static)
        var gradient = ctx.createRadialGradient(W/2, H/2, 0, W/2, H/2, Math.max(W, H)*0.7);
        gradient.addColorStop(0, '{accent_glow}');
        gradient.addColorStop(1, '{bg_grad}');
        ctx.fillStyle = gradient;
        ctx.fillRect(0, 0, W, H);
        
        // Draw stars with twinkling
        for (var i=0;i<stars.length;i++) {{
            var star = stars[i];
            var twinklePhase = (elapsed / star.twinkleSpeed * Math.PI * 2) + star.twinkleOffset;
            var twinkle = (Math.sin(twinklePhase) + 1) / 2; // 0-1
            var alpha = star.baseBrightness * (0.8 + twinkle * 0.4); // Less variation
            var size = star.size * (0.95 + twinkle * 0.1); // Smaller size variation
            
            // Glow (simplified for performance)
            ctx.globalAlpha = alpha * 0.3;
            ctx.fillStyle='{dot_col}';
            ctx.beginPath();
            ctx.arc(star.x, star.y, size * 1.8, 0, Math.PI * 2);
            ctx.fill();
            
            // Core
            ctx.globalAlpha = alpha;
            ctx.beginPath();
            ctx.arc(star.x, star.y, size, 0, Math.PI * 2);
            ctx.fill();
        }}
        
        // Draw shooting star if active
        if (shootingStar) {{
            shootingStar.x += Math.cos(shootingStar.angle) * shootingStar.speed;
            shootingStar.y += Math.sin(shootingStar.angle) * shootingStar.speed;
            shootingStar.life -= 1;
            shootingStar.opacity = shootingStar.life / 200;
            
            ctx.globalAlpha = shootingStar.opacity * 0.7;
            ctx.strokeStyle = '{dot_col}';
            ctx.lineWidth = 1.2;
            ctx.lineCap = 'round';
            ctx.beginPath();
            ctx.moveTo(shootingStar.x, shootingStar.y);
            ctx.lineTo(
                shootingStar.x - Math.cos(shootingStar.angle) * shootingStar.length,
                shootingStar.y - Math.sin(shootingStar.angle) * shootingStar.length
            );
            ctx.stroke();
            
            // Head glow (simplified)
            ctx.globalAlpha = shootingStar.opacity;
            ctx.beginPath();
            ctx.arc(shootingStar.x, shootingStar.y, 1.5, 0, Math.PI * 2);
            ctx.fill();
            
            if (shootingStar.life <= 0) {{
                shootingStar = null;
            }}
        }}

        animationId = requestAnimationFrame(draw);
    }}

    draw();
"""


def _get_constellation_js(line_col: str, dot_col: str) -> str:
    """Return the JS for drawing the seeded constellation pattern on a canvas with ID 'bg'."""
    return f"""
    var W=cv.width=window.innerWidth, H=cv.height=window.innerHeight;
    var ctx=cv.getContext('2d');

    /* Seeded LCG — deterministic from today's date */
    var d=new Date();
    var seed=(d.getFullYear()*10000+(d.getMonth()+1)*100+d.getDate())*9999991;
    function rand() {{
        seed=(seed*1664525+1013904223)&0x7fffffff;
        return seed/0x7fffffff;
    }}

    /* Point count scales with viewport area, clamped 40–90 */
    var N=Math.round(W*H/14000);
    if (N<40) N=40; if (N>90) N=90;

    var pts=[];
    for (var i=0;i<N;i++) pts.push([rand()*W, rand()*H]);

    /* Connection threshold: ~22% of shortest screen dimension */
    var THRESH=Math.min(W,H)*0.22;

    /* Draw edges — alpha fades with distance */
    ctx.lineWidth=0.6;
    for (var i=0;i<N;i++) {{
        for (var j=i+1;j<N;j++) {{
            var dx=pts[i][0]-pts[j][0], dy=pts[i][1]-pts[j][1];
            var dist=Math.sqrt(dx*dx+dy*dy);
            if (dist<THRESH) {{
                ctx.globalAlpha=(1-dist/THRESH)*0.18;
                ctx.strokeStyle='{line_col}';
                ctx.beginPath();
                ctx.moveTo(pts[i][0],pts[i][1]);
                ctx.lineTo(pts[j][0],pts[j][1]);
                ctx.stroke();
            }}
        }}
    }}

    /* Draw nodes — vary size and alpha per point using the seeded RNG */
    for (var i=0;i<N;i++) {{
        var r=0.8+rand()*1.8;
        ctx.globalAlpha=0.25+rand()*0.45;
        ctx.fillStyle='{dot_col}';
        ctx.beginPath();
        ctx.arc(pts[i][0],pts[i][1],r,0,6.2832);
        ctx.fill();
    }}
"""


def get_background_js(style, line_col, dot_col, dark_mode=True):
    """Return the appropriate JS for the selected background style, wrapped for reliability."""
    if style == "classic":
        script = _get_classic_constellation_js(line_col, dot_col)
    elif style == "current":
        script = _get_constellation_js(line_col, dot_col)
    elif style == "static":
        script = _get_static_network_js(line_col, dot_col)
    elif style == "atmospheric":
        script = _get_atmospheric_sky_js(line_col, dot_col, dark_mode)
    else:
        script = _get_constellation_js(line_col, dot_col)
    return _wrap_background_script(script)
