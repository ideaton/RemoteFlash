"""
RemoteFlash — AVR device-signature database.

Maps the 3-byte device signature (hex, lowercase) reported by avrdude to the
avrdude part id and a human-readable chip name.
"""

# signature → (avrdude part id, human name)
AVR_SIGNATURES = {
    "1e950f": ("m328p", "ATmega328P"),
    "1e9514": ("m328", "ATmega328"),
    "1e9516": ("m328pb", "ATmega328PB"),
    "1e9406": ("m168", "ATmega168"),
    "1e940b": ("m168p", "ATmega168P"),
    "1e9307": ("m8", "ATmega8"),
    "1e9403": ("m16", "ATmega16"),
    "1e9502": ("m32", "ATmega32"),
    "1e9602": ("m64", "ATmega64"),
    "1e9609": ("m644", "ATmega644"),
    "1e960a": ("m644p", "ATmega644P"),
    "1e9702": ("m128", "ATmega128"),
    "1e9703": ("m1280", "ATmega1280"),
    "1e9704": ("m1281", "ATmega1281"),
    "1e9705": ("m1284p", "ATmega1284P"),
    "1e9801": ("m2560", "ATmega2560"),
    "1e9802": ("m2561", "ATmega2561"),
    "1e9587": ("m32u4", "ATmega32U4"),
    "1e9205": ("m48", "ATmega48"),
    "1e920a": ("m48p", "ATmega48P"),
    "1e9308": ("m8535", "ATmega8535"),
    "1e9306": ("m8515", "ATmega8515"),
    "1e9007": ("t13", "ATtiny13"),
    "1e910a": ("t2313", "ATtiny2313"),
    "1e9206": ("t45", "ATtiny45"),
    "1e930b": ("t85", "ATtiny85"),
    "1e910b": ("t24", "ATtiny24"),
    "1e9207": ("t44", "ATtiny44"),
    "1e930c": ("t84", "ATtiny84"),
}
