import Foundation
import iTunesLibrary

let library = try ITLibrary(apiVersion: "1.1")

print("persistent_id\ttitle\tartist\talbum\turl")

for playlist in library.allPlaylists where playlist.name == "Favorite Songs" {
    fputs("# playlist=\(playlist.name) items=\(playlist.items.count) kind=\(playlist.distinguishedKind.rawValue)\n", stderr)

    for item in playlist.items {
        let id = item.persistentID.stringValue
        let title = item.title
        let artist = item.artist?.name ?? ""
        let album = item.album.title ?? ""
        let location = item.location?.absoluteString ?? ""

        print([id, title, artist, album, location].joined(separator: "\t"))
    }
}
