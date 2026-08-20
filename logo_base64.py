"""
科技风Logo和头像的base64编码资源
可以直接在Streamlit中使用
"""
import base64

# 科技风Logo (SVG转base64)
TECH_LOGO_SVG = '''
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 200 200" width="200" height="200">
  <defs>
    <linearGradient id="bg" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" style="stop-color:#0a1628;stop-opacity:1" />
      <stop offset="100%" style="stop-color:#1a1f3a;stop-opacity:1" />
    </linearGradient>
    <linearGradient id="glow" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" style="stop-color:#00d4ff;stop-opacity:1" />
      <stop offset="100%" style="stop-color:#00ffd5;stop-opacity:1" />
    </linearGradient>
    <filter id="glow-effect">
      <feGaussianBlur stdDeviation="3" result="blur"/>
      <feMerge>
        <feMergeNode in="blur"/>
        <feMergeNode in="SourceGraphic"/>
      </feMerge>
    </filter>
  </defs>
  
  <!-- 背景 -->
  <rect width="200" height="200" fill="url(#bg)"/>
  
  <!-- 外发光六边形 -->
  <polygon points="100,20 170,60 170,140 100,180 30,140 30,60" 
           fill="none" stroke="#00d4ff" stroke-width="3" opacity="0.3" filter="url(#glow-effect)"/>
  
  <!-- 主六边形 -->
  <polygon points="100,30 160,65 160,135 100,170 40,135 40,65" 
           fill="#1a1f3a" stroke="url(#glow)" stroke-width="2.5" filter="url(#glow-effect)"/>
  
  <!-- 内部六边形 -->
  <polygon points="100,50 145,75 145,125 100,150 55,125 55,75" 
           fill="none" stroke="#00ffd5" stroke-width="1.5" opacity="0.6"/>
  
  <!-- 中心点 -->
  <circle cx="100" cy="100" r="6" fill="#00d4ff" filter="url(#glow-effect)"/>
  
  <!-- CT字母 -->
  <text x="100" y="95" text-anchor="middle" font-family="Arial, sans-serif" 
        font-size="28" font-weight="bold" fill="white" filter="url(#glow-effect)">CT</text>
  
  <!-- 装饰线条 -->
  <line x1="50" y1="50" x2="25" y2="25" stroke="#00d4ff" stroke-width="1.5" opacity="0.5"/>
  <line x1="150" y1="50" x2="175" y2="25" stroke="#00d4ff" stroke-width="1.5" opacity="0.5"/>
  <line x1="50" y1="150" x2="25" y2="175" stroke="#00d4ff" stroke-width="1.5" opacity="0.5"/>
  <line x1="150" y1="150" x2="175" y2="175" stroke="#00d4ff" stroke-width="1.5" opacity="0.5"/>
  
  <!-- 角点装饰 -->
  <circle cx="30" cy="60" r="3" fill="#00ffd5"/>
  <circle cx="170" cy="60" r="3" fill="#00ffd5"/>
  <circle cx="30" cy="140" r="3" fill="#00ffd5"/>
  <circle cx="170" cy="140" r="3" fill="#00ffd5"/>
</svg>
'''

# 用户头像SVG
USER_AVATAR_SVG = '''
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100" width="100" height="100">
  <defs>
    <linearGradient id="avatar-bg" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" style="stop-color:#00d4ff;stop-opacity:1" />
      <stop offset="100%" style="stop-color:#0066cc;stop-opacity:1" />
    </linearGradient>
    <filter id="avatar-glow">
      <feGaussianBlur stdDeviation="2" result="blur"/>
      <feMerge>
        <feMergeNode in="blur"/>
        <feMergeNode in="SourceGraphic"/>
      </feMerge>
    </filter>
  </defs>
  
  <!-- 外发光环 -->
  <circle cx="50" cy="50" r="48" fill="none" stroke="#00d4ff" stroke-width="2" opacity="0.3" filter="url(#avatar-glow)"/>
  
  <!-- 主背景圆 -->
  <circle cx="50" cy="50" r="45" fill="url(#avatar-bg)"/>
  
  <!-- 内边框 -->
  <circle cx="50" cy="50" r="42" fill="none" stroke="#00ffd5" stroke-width="1" opacity="0.5"/>
  
  <!-- 用户图标 -->
  <circle cx="50" cy="38" r="14" fill="white" opacity="0.9"/>
  <path d="M25,85 Q25,60 50,60 Q75,60 75,85 Z" fill="white" opacity="0.9"/>
  
  <!-- 发光效果 -->
  <circle cx="50" cy="38" r="14" fill="none" stroke="#00d4ff" stroke-width="1" filter="url(#avatar-glow)"/>
</svg>
'''

# 科技风小图标
TECH_ICON_SVG = '''
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64" width="64" height="64">
  <defs>
    <linearGradient id="icon-bg" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" style="stop-color:#0a1628;stop-opacity:1" />
      <stop offset="100%" style="stop-color:#1a1f3a;stop-opacity:1" />
    </linearGradient>
  </defs>
  
  <circle cx="32" cy="32" r="30" fill="url(#icon-bg)" stroke="#00d4ff" stroke-width="2"/>
  <text x="32" y="40" text-anchor="middle" font-family="Arial" font-size="20" 
        font-weight="bold" fill="#00d4ff">CT</text>
</svg>
'''


def get_logo_base64():
    """获取Logo的base64编码"""
    return base64.b64encode(TECH_LOGO_SVG.encode('utf-8')).decode('utf-8')


def get_avatar_base64():
    """获取头像的base64编码"""
    return base64.b64encode(USER_AVATAR_SVG.encode('utf-8')).decode('utf-8')


def get_logo_data_url():
    """获取Logo的data URL"""
    return f"data:image/svg+xml;base64,{get_logo_base64()}"


def get_avatar_data_url():
    """获取头像的data URL"""
    return f"data:image/svg+xml;base64,{get_avatar_base64()}"


def get_logo_html(size=100):
    """获取Logo的HTML代码"""
    return f'<img src="{get_logo_data_url()}" width="{size}" height="{size}" style="filter: drop-shadow(0 0 10px rgba(0,212,255,0.5))"/>'


def get_avatar_html(size=50):
    """获取头像的HTML代码"""
    return f'<img src="{get_avatar_data_url()}" width="{size}" height="{size}" style="border-radius: 50%; filter: drop-shadow(0 0 8px rgba(0,212,255,0.5))"/>'
