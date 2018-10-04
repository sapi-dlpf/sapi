# Isto aqui é para "embaralhar" o sapí.info
# O intuito é levar para o sapi_cellebrite, e aplicar no sapi.info
def teste5():
    from cryptography.fernet import Fernet

    import hashlib
    import base64

    #key = Fernet.generate_key()

    my_password = 'swordfish'
    key = hashlib.md5(my_password.encode('utf-8')).hexdigest()
    print(key)
    print(base64.urlsafe_b64encode(key.encode('utf-8')))

    key_64 = base64.urlsafe_b64encode(key.encode('utf-8'))
    print(key)
    cipher_suite = Fernet(key_64)
    cipher_text = cipher_suite.encrypt(b"Mensagem secreta.")
    print(cipher_text)

    plain_text = cipher_suite.decrypt(cipher_text)
    print("== plain_text ==")
    print(plain_text)
    return
