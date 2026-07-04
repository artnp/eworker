    if mode_flag == "--clean":
        process_clean_only(target_path)
    elif mode_flag in ["--donate", "--donate-no-paste"]:
        process_donate(target_path)
    else:
        process_donate()