# Jellyfin Links

`jellyfin_links.py` 将同一季的已下载视频整理成 Jellyfin 可扫描的剧集目录。脚本使用相对软链接，原视频保留在下载目录。需要 Python 3 和支持软链接的文件系统。

## 预览和生成

假设原视频放在 `/srv/media/downloads/Example Show`，剧集库位于 `/srv/media/library`。源目录和剧集库必须是互不包含的目录树。脚本只扫描源目录的当前层，默认识别 `Example Show - 01 [1080p].mkv` 这类文件名中的集号。

先运行预览，查看 `LINK` 计划。预览不会创建目录或链接。

```bash
python3 jellyfin_links.py "/srv/media/downloads/Example Show" /srv/media/library \
  --title "Example Show" --season 1
```

确认后加上 `--apply`。

```bash
python3 jellyfin_links.py "/srv/media/downloads/Example Show" /srv/media/library \
  --title "Example Show" --season 1 --apply
```

示例生成 `/srv/media/library/Example Show/Season 01/Example Show - S01E01.mkv`。重复运行时，目标相同的链接会显示 `KEEP`。同一集匹配到多个文件，或输出路径已被其他文件或链接占用时，脚本会报告 `CONFLICT` 并在写入前退出。

如果源文件从第 13 集开始编号，而这一季在 Jellyfin 中应从第 1 集开始，使用 `--episode-offset -12`。其他命名格式可以通过 `--pattern` 指定匹配文件名主干的正则表达式，表达式必须包含名为 `episode` 的捕获组。

## 让 Jellyfin 容器访问原视频

软链接的目标是相对于链接所在目录计算的。将宿主机上包含源目录和剧集库的公共父目录挂载到容器中，即可保留两者之间的相对路径。以 Docker Compose 为例，在现有 Jellyfin 服务的 `volumes` 中加入以下挂载。

```yaml
services:
  jellyfin:
    volumes:
      - /srv/media:/media:ro
```

在 Jellyfin 中添加电视剧媒体库，将扫描目录设为 `/media/library`。容器通过软链接读取 `/media/downloads/Example Show` 下的原视频。Jellyfin 进程需要有权限遍历相关目录并读取原文件。只挂载 `library` 会使容器内的链接找不到原视频。
