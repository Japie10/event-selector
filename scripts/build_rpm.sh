#!/bin/bash
# Build RPM package for Event Selector

set -e

# Configuration
NAME="event-selector"
VERSION=$(python -c "from src.event_selector import __version__; print(__version__)")
RELEASE="1"
ARCH="noarch"
PYTHON_VERSION="3.12"

# Paths
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
BUILD_DIR="$PROJECT_DIR/build/rpm"
SPEC_FILE="$BUILD_DIR/SPECS/${NAME}.spec"

echo "Building RPM for ${NAME} version ${VERSION}"

# Create RPM build structure
mkdir -p "$BUILD_DIR"/{BUILD,RPMS,SOURCES,SPECS,SRPMS}

# Create wheel and source distribution
echo "Creating Python distributions..."
cd "$PROJECT_DIR"
python -m build --wheel --sdist

# Bundle dependencies
echo "Downloading dependencies..."
pip download \
    --dest "$BUILD_DIR/SOURCES/wheels" \
    --only-binary :all: \
    --python-version ${PYTHON_VERSION} \
    --platform manylinux2014_x86_64 \
    PyQt5 PyYAML pydantic numpy loguru python-json-logger

# Copy our wheel
cp dist/*.whl "$BUILD_DIR/SOURCES/wheels/"

# Create tarball of the project
echo "Creating source tarball..."
tar czf "$BUILD_DIR/SOURCES/${NAME}-${VERSION}.tar.gz" \
    --exclude='.git' \
    --exclude='build' \
    --exclude='dist' \
    --exclude='*.egg-info' \
    --exclude='__pycache__' \
    -C "$PROJECT_DIR" .

# Generate RPM spec file
echo "Generating spec file..."
cat > "$SPEC_FILE" << EOF
Name:           ${NAME}
Version:        ${VERSION}
Release:        ${RELEASE}%{?dist}
Summary:        Hardware/Firmware Event Mask Management Tool

License:        MIT
URL:            https://github.com/yourusername/${NAME}
Source0:        ${NAME}-${VERSION}.tar.gz

BuildArch:      noarch
BuildRequires:  python3-devel >= 3.12
BuildRequires:  python3-pip
BuildRequires:  python3-wheel

Requires:       python3 >= 3.12
Requires:       python3-pip

%description
Event Selector is a modern desktop tool for managing hardware/firmware 
event masks and capture-masks. It provides comprehensive support for 
two YAML-based event definition formats (mk1 and mk2), with a powerful 
GUI featuring filtering, tri-state selection, undo/redo, and robust validation.

%prep
%setup -q -n ${NAME}-${VERSION}

%build
# Nothing to build, using pre-built wheels

%install
# Create installation directories
mkdir -p %{buildroot}%{_libdir}/${NAME}
mkdir -p %{buildroot}%{_bindir}
mkdir -p %{buildroot}%{_datadir}/applications
mkdir -p %{buildroot}%{_datadir}/icons/hicolor/scalable/apps

# Copy wheels to installation directory
cp -r %{_sourcedir}/wheels %{buildroot}%{_libdir}/${NAME}/

# Create wrapper scripts
cat > %{buildroot}%{_bindir}/${NAME} << 'WRAPPER'
#!/bin/bash
# Wrapper script for Event Selector CLI

# Ensure pip packages are installed
if [ ! -f /usr/lib/${NAME}/.installed ]; then
    echo "Installing Event Selector packages..."
    python3 -m pip install --no-index --find-links /usr/lib/${NAME}/wheels ${NAME}
    touch /usr/lib/${NAME}/.installed
fi

exec python3 -m event_selector.cli.app "\$@"
WRAPPER

cat > %{buildroot}%{_bindir}/${NAME}-gui << 'WRAPPER'
#!/bin/bash
# Wrapper script for Event Selector GUI

# Ensure pip packages are installed  
if [ ! -f /usr/lib/${NAME}/.installed ]; then
    echo "Installing Event Selector packages..."
    python3 -m pip install --no-index --find-links /usr/lib/${NAME}/wheels ${NAME}
    touch /usr/lib/${NAME}/.installed
fi

exec python3 -m event_selector.gui.main_window "\$@"
WRAPPER

chmod 755 %{buildroot}%{_bindir}/${NAME}
chmod 755 %{buildroot}%{_bindir}/${NAME}-gui

# Create desktop file
cat > %{buildroot}%{_datadir}/applications/${NAME}.desktop << 'DESKTOP'
[Desktop Entry]
Name=Event Selector
Comment=Hardware/Firmware Event Mask Management Tool
Exec=${NAME}-gui %f
Icon=${NAME}
Terminal=false
Type=Application
Categories=Development;Engineering;
MimeType=text/x-yaml;
DESKTOP

%files
%license LICENSE
%doc README.md CHANGELOG.md
%{_bindir}/${NAME}
%{_bindir}/${NAME}-gui
%{_libdir}/${NAME}/
%{_datadir}/applications/${NAME}.desktop

%changelog
* $(date '+%a %b %d %Y') Your Name <your.email@example.com> - ${VERSION}-${RELEASE}
- Initial RPM release

EOF

# Build the RPM
echo "Building RPM package..."
rpmbuild --define "_topdir $BUILD_DIR" -ba "$SPEC_FILE"

# Copy RPM to dist directory
echo "Copying RPM to dist..."
mkdir -p "$PROJECT_DIR/dist"
cp "$BUILD_DIR/RPMS/${ARCH}/"*.rpm "$PROJECT_DIR/dist/"

echo "RPM build complete!"
echo "Package: $PROJECT_DIR/dist/${NAME}-${VERSION}-${RELEASE}.${ARCH}.rpm"