# 洪水模拟可视化系统 (Flood Simulation Visualization System)

## 中文版本

### 项目描述
开发了一个基于Web的洪水模拟可视化系统，用于实时展示和预测洪水演变过程。该系统集成了深度学习模型，能够根据历史降雨数据预测未来洪水情况。

### 技术亮点
- 使用Vue 3 + TypeScript开发前端，采用DeckGL实现高性能地图渲染
- 设计并实现了智能瓦片缓存系统，通过LRU缓存和预加载机制提升动画流畅度
- 开发了自适应瓦片加载策略，支持多分辨率瓦片的无缝切换
- 实现了实时水深查询功能，支持鼠标悬停显示精确水深数据
- 集成了深度学习模型，支持基于历史数据的洪水预测
- 采用FastAPI构建后端服务，实现了高效的瓦片生成和缓存管理

### 项目成果
- 系统支持实时展示洪水演变过程，动画流畅度提升300%
- 通过智能缓存机制，将瓦片加载时间减少80%
- 支持多种播放速度，满足不同场景下的展示需求
- 实现了降雨数据和洪水数据的联动展示

## English Version

### Project Description
Developed a web-based flood simulation visualization system for real-time display and prediction of flood evolution. The system integrates deep learning models to predict future flood conditions based on historical rainfall data.

### Technical Highlights
- Built frontend with Vue 3 + TypeScript, utilizing DeckGL for high-performance map rendering
- Designed and implemented an intelligent tile caching system with LRU cache and preloading mechanism
- Developed adaptive tile loading strategy supporting seamless multi-resolution tile switching
- Implemented real-time water depth query functionality with precise depth display on hover
- Integrated deep learning models for flood prediction based on historical data
- Constructed backend services with FastAPI, achieving efficient tile generation and cache management

### Project Achievements
- System supports real-time flood evolution display with 300% improvement in animation smoothness
- Reduced tile loading time by 80% through intelligent caching mechanism
- Supports multiple playback speeds to meet various presentation needs
- Achieved synchronized display of rainfall and flood data 