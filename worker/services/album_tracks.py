from __future__ import annotations

from ytmusicapi import YTMusic

from services.search_pickers import _pick_single_video_id


def _album_track_video_ids(ytmusic: YTMusic, browse_id: str) -> list[str]:
    album = ytmusic.get_album(browse_id)
    tracks = album.get("tracks") or []
    video_ids: list[str] = []
    for track in tracks:
        video_id = track.get("videoId")
        if video_id:
            video_ids.append(video_id)
    return video_ids


def _album_audio_only_video_ids(
    ytmusic: YTMusic, browse_id: str, release_artist_name: str
) -> tuple[list[str], int]:
    album = ytmusic.get_album(browse_id)
    tracks = album.get("tracks") or []
    audio_video_ids: list[str] = []
    fallback_failures = 0

    for track in tracks:
        track_video_id = track.get("videoId")
        track_title = str(track.get("title", "")).strip()
        track_artists = track.get("artists") or []
        primary_track_artist = (
            str(track_artists[0].get("name", "")).strip()
            if track_artists
            else release_artist_name
        )

        # When album track points to a music video, force a song-only fallback.
        if track_video_id:
            try:
                track_details = ytmusic.get_song(track_video_id) or {}
                video_details = track_details.get("videoDetails") or {}
                if str(video_details.get("musicVideoType", "")).upper() == "MUSIC_VIDEO":
                    track_video_id = None
            except Exception:
                # If metadata lookup fails, fallback to strict search path.
                track_video_id = None

        if track_video_id:
            audio_video_ids.append(track_video_id)
            continue

        if not track_title:
            fallback_failures += 1
            continue

        fallback_query = f"{track_title} {primary_track_artist}".strip()
        try:
            search_results = ytmusic.search(fallback_query, filter="songs", limit=5)
            fallback_video_id = _pick_single_video_id(
                search_results, primary_track_artist, track_title
            )
        except Exception:
            fallback_video_id = None

        if fallback_video_id:
            audio_video_ids.append(fallback_video_id)
        else:
            fallback_failures += 1

    return audio_video_ids, fallback_failures
