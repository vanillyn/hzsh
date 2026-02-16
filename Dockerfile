FROM archlinux:latest

RUN pacman -Syu --noconfirm && \
    pacman -S --noconfirm base-devel git vim nano curl wget python python-pip nodejs npm fastfetch inetutils coreutils && \
    pacman -Scc --noconfirm

RUN useradd -m -s /bin/bash default

WORKDIR /home/default

CMD ["/bin/bash"]
